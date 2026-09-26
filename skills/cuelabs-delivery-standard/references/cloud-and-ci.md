# Cloud and CI standard

## Contents

- CueLABS cloud and environment policy
- GitHub Actions workflow families
- Test layout and fleet parity
- Email, data plane, and protocol decisions

## Canon

- Backends deploy to GCP Cloud Run (provisioned via the `cuesoft-iac` Pulumi
  ecosystem — never ad-hoc); frontends deploy to Firebase App Hosting; the
  Helm chart remains the self-host path.
- **Serverless functions are reserved for probe/health-check style endpoints
  only** — real request handling and business logic always live in a
  containerized `api/<service>`, never split out into an ad-hoc Cloud
  Function.
- AI features use **Vertex AI** (Gemini via `aiplatform.googleapis.com`, ADC —
  see `cuesoft-iac/functions/cueprise-gemini-proxy`); no consumer AI-vendor
  API keys in cloud deployments. Self-host fallback: BYO Gemini/Groq env keys.
- Environments & deploy gating: `stg` = sandbox is the ONLY environment for
  CueLABS™ products (no production); Doppler config `stg` holds its secrets.
  Deploys are scoped by surface: the WEBSITES ride Firebase App Hosting
  automatic rollouts from `main` (declared as appHosting backends in
  `cuesoft-iac`, `rootDirectory: /web`, Cloudflare-proxied; a web-visible
  merge is live within about 30 minutes). API-SERVICE deploys are the
  tag-gated path: they fire **only on `v*` tag creation**, gated by a
  tag ruleset (owner-level) + protected GitHub environment, via
  `release.yml` (added with the product's deploy phase). GitHub Actions
  itself never deploys the sites.
- **GitHub Actions standard (uniform across repos)**:
  standardized workflow families with identical shared jobs and conventions —
  `.github/workflows/build-and-test.yml` (workflow name `build-and-test`;
  triggers `push: branches [main]` + `pull_request`, no path filters —
  build-ready surfaces join as jobs; `permissions: contents: read`; `concurrency:
  build-and-test-${{ github.ref }}` with cancel-in-progress; one job per
  surface: `web` = "web · lint + typecheck + unit + build" on Node 24
  (`npm ci → lint → typecheck → test → build`), `web-e2e` = "web ·
  Playwright (TEST_MODE)" (`playwright install --with-deps chromium →
  test:e2e`). API jobs land when a product backend reaches its build-ready
  phase; mobile jobs land when mobile implementation begins. Once present,
  stack-equivalent API/mobile jobs follow the same fleet naming, setup, cache,
  and command shape; action steps
  pin the LATEST major of official actions — currently
  `actions/checkout@v7`, `actions/setup-node@v7`,
  `actions/upload-artifact@v7` (verify via
  `gh api repos/actions/<name>/releases/latest` when touching workflows,
  never copy stale versions from older files). **Shared web jobs are
  BYTE-IDENTICAL across repos** — repo variance lives in `package.json`
  scripts, never in workflow YAML; a mobile product's file additionally
  carries its mobile jobs (and the two ratified mobile workflows,
  `mobile-goldens` dispatch + `mobile-e2e` nightly — see
  `$cuelabs-mobile-standard`); named steps only (Checkout · Setup Node ·
  Install dependencies · Lint · Typecheck · Unit & integration tests ·
  Build (TEST_MODE with `NEXT_PUBLIC_TEST_MODE: "1"`)); the e2e job builds
  in TEST_MODE, installs chromium, runs `test:e2e` with TEST_MODE+CI env,
  and uploads `web/playwright-report` as artifact `playwright-report`
  (retention 7) on failure) and the tag-gated `release.yml` (added with the
  product's deploy phase). Workflow files beyond these families and
  explicitly ratified surface workflows are a standards deviation and need
  ratification. CodeQL runs via GitHub DEFAULT SETUP
  (a repo setting, `gh api repos/<org>/<repo>/code-scanning/default-setup`),
  not a workflow file — parity audits check the API, not `.github/`.
- **Test layout standard (uniform across repos)**: unit/
  integration tests co-locate with their source as `<name>.test.ts(x)`
  (component `Button.test.tsx` beside `Button.tsx`; kebab for module tests);
  Playwright e2e specs live in `web/e2e/<flow>.spec.ts` (flow names mirror
  `design.md`'s prototype journeys) with `playwright.config.ts` at the
  web root; npm scripts are `test` (unit), `test:e2e` (Playwright), `lint`,
  `typecheck` in every web app.
- **Fleet parity canons**:
  - **Node 24 single-truth**: `setup-node` in CI, `web/.nvmrc`, the web
    Dockerfile (`node:24-slim`), and the README prerequisite all say 24;
    `@types/node` tracks the runtime major (`^24`). No repo states a
    different floor anywhere.
  - **Go single-truth**: one fleet Go version (currently `go 1.26` in
    go.mod, `golang:1.26-alpine` images); service binaries build as
    `app`; HEALTHCHECK `start-period` 10s (services that load models or
    warm caches at boot may extend it, typically 30–40s, with the reason
    in the Dockerfile).
  - **Web dep alignment**: `next`/`react`/`react-dom`/`eslint-config-next`
    are EXACT-pinned and fleet-identical; remaining shared devDeps stay
    caret but version-aligned across repos; the dependabot npm `ignore`
    block (eslint/typescript/@types/node majors) ships in every repo.
  - **TEST_MODE web canon (extends the session-gate canon)**: provider
    file is `web/src/auth/test-mode-provider.ts`, storage const
    `SESSION_KEY`, key `<product>.test-session`, value = the JSON session
    snapshot (never a bare sentinel; restore validates the payload,
    treats missing/corrupt as signed_out, and re-resolves identity so
    mutable account state is never served stale). Mock server lives at
    `web/src/app/api/mock/v1/`, store at `web/src/mocks/store.ts`, seeds
    at `web/src/mocks/seed.ts`, reset at `POST /api/mock/v1/testing/reset`.
  - **Org lint bans fleet-wide**: `no-restricted-imports` blocks `@mui/*`,
    `@emotion/*`, `dayjs`, `moment` (plus the legacy-path ban) in every
    web app; `eslint-plugin-testing-library` is WIRED (flat/react preset
    scoped to `src/**/*.test.{ts,tsx}`) with `no-container` and
    `no-node-access` disabled via a documenting comment — bespoke
    token-layer components assert non-semantic structure by design.
  - **README fleet template**: badge row (License MIT + build-and-test
    status) after the intro paragraph; prose overview; plain-indent repo
    tree; `cp .env.example .env` + make-target quickstart; Node/Go
    versions per the single-truths above. Root `.env.example` uses
    `── section ──` comment headers; `web/.env.example` stays headerless.
  - **next.config**: `devIndicators: { position: "bottom-right" }` — keep
    the dev indicator, keep it out of content corners.
- Transactional email: **Brevo REST API** only (`BREVO_API_KEY/FROM_EMAIL/
  FROM_NAME` via Doppler) — **no SMTP** in any CueLABS™ product.
- Data plane (cloud): per-product choice of **Aiven Postgres** or **Firestore**
  (Firebase-native/real-time products → Firestore; financial/relational →
  Postgres; recorded in the product's `docs/decisions.md`). Shared **Aiven
  Redis** with `REDIS_DB`-index tenancy per product/config (discrete
  `REDIS_*` vars). **Doppler** is the env source of truth — project per repo,
  configs `dev / dev_personal / stg / prd`. Object storage: the sandbox
  project's default **Cloud Storage** bucket with per-product/env prefixes.
  Self-host compose bundles its own stores.
- Protocols: **HTTP/JSON is the default product API**; gRPC is a
  standardized option wherever a domain needs streaming, telemetry ingest,
  high-throughput internal s2s, or another documented transport requirement.
  Generated protocol clients live in `src/proto/` (with transitional generated
  client paths covered by the fleet `.prettierignore`). Cloud Run requires
  end-to-end HTTP/2 (h2c) for gRPC services. A browser gRPC-Web path needs
  Envoy; prefer HTTP/JSON for browser traffic, and a product's self-host Helm
  chart deploys Envoy only while that product exposes a gRPC-Web path.
- **Pub/sub (Aiven Kafka) is a standardized option** for async multi-language
  processing pipelines where durability across a consumer restart matters
  more than a live round-trip — e.g. a Node gateway handing a file to a
  Python processing service. Preferred over direct gRPC s2s for that shape
  because the queue, not caller-side retry logic, is the durability
  boundary: a message published while its consumer is restarting or
  redeploying is retained and consumed afterwards (Aiven Kafka uses SASL
  SCRAM-SHA-256 + TLS). Env vars: `KAFKA_BROKERS`, `KAFKA_USERNAME`,
  `KAFKA_PASSWORD`, `KAFKA_SSL_CA` (identical names across every language
  client). Each consumer runs its own consumer group. The canonical shape is
  gateway `api/<gateway>` → processing `api/<processor>` → `api/common`.
- **Kafka consumers need a running workload.** A Kafka message does not
  start a Cloud Run instance that has scaled to zero, and under the default
  request-based billing an instance gets no CPU outside a request, so a
  consumer on a default Cloud Run service stops consuming. Every Kafka
  consumer runs as one of:
  - a **Cloud Run worker pool** (the default: always-on, no HTTP ingress);
  - a Cloud Run service with `min-instances >= 1` **and** instance-based
    billing (CPU always allocated);
  - another explicit wake-up path, documented in the product's
    `docs/deployment.md` with how queued messages are drained after a wake.

  Record the always-on cost against any free-tier goal. See Google's
  [instance autoscaling](https://docs.cloud.google.com/run/docs/about-instance-autoscaling)
  notes for the scale-from-zero and background-CPU limits.
- **gRPC s2s client resilience on Cloud Run**: Cloud Run
  scale-to-zero and instance recycling can sever the underlying HTTP/2
  connection without a graceful gRPC goodbye, leaving a channel that looks
  alive but hangs calls. Every gRPC client (Node, Go, Python):
  - sets a **deadline on every call**, so no call can hang indefinitely;
  - declares a **[retry policy](https://grpc.io/docs/guides/retry/)** in its
    service config for methods that are safe to retry (idempotent reads and
    idempotent writes only): a bounded `maxAttempts`, exponential backoff,
    and `retryableStatusCodes` limited to `UNAVAILABLE`. `waitForReady: false`
    is not a retry policy; it is the default fail-fast behavior;
  - sets **[keepalive](https://grpc.io/docs/guides/keepalive/)**
    (`grpc.keepalive_time_ms`/`keepalive_timeout_ms` or the language
    equivalent) to detect a dead connection during active calls. Pings on
    an idle connection need `keepalive_permit_without_calls` and a ping
    interval the peer accepts (on Cloud Run the peer is Google's front end,
    not the service), so do not rely on idle detection: the deadline and
    retry policy are the guarantee.

  Required for any product that keeps Cloud Run services scaled to zero
  between calls (the default posture for request-driven services).
