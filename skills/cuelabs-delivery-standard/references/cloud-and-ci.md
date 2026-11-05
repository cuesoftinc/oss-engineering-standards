# Cloud and CI standard

## Contents

- CueLABS cloud and environment policy
- GitHub Actions workflow families
- Test layout and fleet parity
- Email, data plane, and protocol decisions

## Canon

- Backends deploy to GCP Cloud Run (provisioned via the
  infrastructure-as-code (IaC) stack — never ad-hoc); frontends deploy to Firebase App Hosting; the
  Helm chart remains the self-host path.
- **Serverless functions are reserved for probe/health-check style endpoints
  only** — real request handling and business logic always live in a
  containerized `api/<service>`, never split out into an ad-hoc Cloud
  Function.
- AI features use **Vertex AI** (Gemini via `aiplatform.googleapis.com`, ADC,
  through a server-side proxy under its own service account); no consumer AI-vendor
  API keys in cloud deployments. Self-host fallback: BYO Gemini/Groq env keys.
- Environments & deploy gating: `stg` = sandbox is the ONLY environment for
  CueLABS™ products (no production); the `stg` config in your secrets manager holds its secrets.
  Deploys are scoped by surface: the WEBSITES ride Firebase App Hosting
  automatic rollouts from `main` (declared as appHosting backends in
  the IaC stack, `rootDirectory: /web`; a web-visible
  merge is live within about 30 minutes). API-SERVICE deploys run on
  **merge to `main`**: every product with a backend carries `release.yml`,
  which triggers on `push` to `main` filtered to `api/**`,
  `.github/workflows/release.yml` and `.github/scripts/**` (plus any other
  image source the product builds, such as `functions/**` for probes or a
  collector image's build files), runs in the `Sandbox` environment as an
  `images · build + push` job and a `deploy · Cloud Run (Sandbox)` job,
  pushes `<org>/<repo>-api-<service>` images tagged with the short sha and
  `latest`, and points the existing Cloud Run services at the new digests.
  No version tags or GitHub releases are cut while products have no
  production. GitHub Actions itself never deploys the sites.
- **Cloud Run resources come from the IaC stack.** Each service is declared
  there with `image: us-docker.pkg.dev/cloudrun/container/hello` only until
  the product's image is in the container registry, then `<org>/<image>:latest`; CI
  deploys by digest afterwards. `minInstances` is omitted (Cloud Run's
  default is 0): every service scales to zero, with no always-on instance
  and no worker pool. `DOCKER_USERNAME` and `DOCKER_PASSWORD` live in
  the secrets manager's CI scope and reach each product's `ci` config as references.
- **Sweeps are Cloud Scheduler jobs**: each calls
  `POST /internal/jobs/<name>` on `api-common` with an OIDC token for the
  product's runtime account. The IaC stack declares them per product
  (`jobPrefix: <product>`, one `{ name, schedule }` per job) in the same
  change that ships the handler; a job is never declared ahead of it.
- **Private services are called with an ID token.** A Cloud Run service
  that is not public lists its callers' service accounts as `invokers` in
  the IaC stack; each caller fetches a Google ID token from the metadata
  server with the target's URL as the audience, caches it until a few
  minutes before it expires, and sends it as `Authorization: Bearer`.
  Local and self-host runs skip the token (no `K_SERVICE`).
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
  pin the LATEST major tag of official actions, never a commit sha — currently
  `actions/checkout@v7`, `actions/setup-node@v7`,
  `actions/upload-artifact@v7` (verify via
  `gh api repos/actions/<name>/releases/latest` when touching workflows,
  never copy stale versions from older files). **Shared web jobs are
  BYTE-IDENTICAL across repos**, repo variance lives in `package.json`
  scripts, never in workflow YAML; a mobile product's file additionally
  carries its mobile jobs (and the two ratified mobile workflows,
  `mobile-goldens` dispatch + `mobile-e2e` nightly, see
  `$cuelabs-mobile-standard`); named steps only (Checkout · Setup Node ·
  Install dependencies · Lint · Typecheck · Unit & integration tests ·
  Build (TEST_MODE with `NEXT_PUBLIC_TEST_MODE: "1"`)); the e2e job builds
  in TEST_MODE, installs chromium, runs `test:e2e` with TEST_MODE+CI env,
  and uploads `web/playwright-report` as artifact `playwright-report`
  (retention 7) on failure) and the `release.yml` that deploys the APIs on
  merge to `main`. Workflow files beyond these families and
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
- Transactional email: **Brevo REST API** only (`BREVO_API_KEY`,
  `BREVO_FROM_EMAIL` and `BREVO_FROM_NAME` via your secrets manager), **no SMTP** in any CueLABS™ product.
- Data plane (cloud): per-product choice of **managed Postgres** or **Firestore**
  (Firebase-native/real-time products → Firestore; financial/relational →
  Postgres; recorded in the product's `docs/decisions.md`). Shared **managed
  Redis** with one ACL user per product, limited to keys under
  `<product>:` (`REDIS_KEY_PREFIX`) and its own channels (discrete
  `REDIS_*` vars). Telemetry and analytics stores use **managed ClickHouse**
  (one service per product, idle scaling so an unused service costs
  nothing, TLS on 8443): the IaC stack owns the service, database and users,
  and the product's migrations own the tables and row policies. Three users
  with one password each: an admin user for migrations
  (`CLICKHOUSE_MIGRATE_USER`), a loader that may only insert
  (`CLICKHOUSE_LOADER_USER`), and a read-only query user under a
  `readonly` profile (`CLICKHOUSE_QUERY_USER`), all against
  `CLICKHOUSE_URL`. A service that migrates at boot exits when the store is
  stopped, so a product's ClickHouse service is never stopped while the
  product is deployed. In `stg`, Firestore products use the sandbox's
  `sandbox` database and Postgres products get a database on the shared
  managed Postgres service, all connecting as the shared `<app_user>` (no
  per-product database users). The IaC stack creates the database owned by
  `<admin_user>`; `<admin_user>` runs `ALTER DATABASE <product> OWNER TO <app_user>;`
  once, so the app's migrations own their tables and `FORCE ROW LEVEL
  SECURITY` applies (`<app_user>` has no `BYPASSRLS`). **Your secrets manager** is the env source of truth: one project per
  repo with configs `dev` (plus personal branches), `stg`, `prd` and `ci`.
  Every deployed surface reads `stg`; `prd` stays empty while products have
  no production; `ci` holds only what GitHub Actions needs. Object storage:
  the sandbox
  project's default **Cloud Storage** bucket with per-product/env prefixes,
  read and written through **signed URLs only** (no public objects).
  Self-host compose bundles its own stores. The web app reaches the API
  through its own `/api/v1` proxy to `api-common`.
- Protocols: **HTTP/JSON is the default product API**; gRPC is a
  standardized option wherever a domain needs streaming, telemetry ingest,
  high-throughput internal s2s, or another documented transport requirement.
  Generated protocol clients live in `src/proto/` (with transitional generated
  client paths covered by the fleet `.prettierignore`). Cloud Run requires
  end-to-end HTTP/2 (h2c) for gRPC services. A browser gRPC-Web path needs
  Envoy; prefer HTTP/JSON for browser traffic, and a product's self-host Helm
  chart deploys Envoy only while that product exposes a gRPC-Web path.
  The deployed `stg` estate runs no Envoy.
- **Pub/sub (managed Kafka) is a standardized option** for async multi-language
  processing pipelines where durability across a consumer restart matters
  more than a live round-trip — e.g. a Node gateway handing a file to a
  Python processing service. Preferred over direct gRPC s2s for that shape
  because the queue, not caller-side retry logic, is the durability
  boundary: a message published while its consumer is restarting or
  redeploying is retained and consumed afterwards (the managed Kafka service uses SASL
  SCRAM-SHA-256 + TLS). Env vars: `KAFKA_BROKERS`, `KAFKA_USERNAME`,
  `KAFKA_PASSWORD`, `KAFKA_SSL_CA` (identical names across every language
  client). Each consumer runs its own consumer group. The canonical shape is
  gateway `api/<gateway>` → processing `api/<processor>` → `api/common`.
  **Every product shares one Kafka service** (like the shared Redis): its
  lanes, envelope, limits, scale-to-zero wake-ups and keep-alive owner are
  in [shared-messaging.md](shared-messaging.md); a product never creates its
  own topics. Only the deployed `stg` services use the shared service; local
  compose and self-host stacks run their own broker.
- **Kafka consumers run at min 0 with request-based CPU.** A Kafka message
  does not start a Cloud Run instance that has scaled to zero, and an
  instance gets CPU only inside a request, so nothing is billed while a
  product is idle and work that must finish happens inside a request:
  whatever publishes for a consumer sends it a `GET /health` that carries
  no data (a **wake-up**), the consumer works while Cloud Run keeps the
  instance, and the owner's scheduled sweep finishes what a wake-up left
  (it re-wakes services while its store shows work in flight, or calls the
  consumer's `POST /internal/settle`, which answers once its lanes are
  caught up) ([shared-messaging.md](shared-messaging.md), "Scale to
  zero"). Worker pools, CPU always allocated and `min-instances >= 1` are
  not used: nothing is always on.
  Document the wake-up wiring in `docs/deployment.md`. See Google's
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
