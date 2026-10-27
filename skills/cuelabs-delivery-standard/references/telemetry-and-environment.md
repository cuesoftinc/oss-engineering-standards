# Telemetry and environment

## Contents

- Telemetry standard
- Environment-variable naming standard

## Telemetry standard (OpenTelemetry)

Every service instruments with **OTel SDKs**: traces (auto-instrumentation
for HTTP/gRPC/DB clients + manual spans on domain operations), custom
metrics (Meter API: counters/histograms per service KPIs), logs (slog/logging
bridges). W3C `traceparent` propagates across all service boundaries.
Export = **direct OTLP from the SDK** (BatchSpan/LogRecord processors);
collector sidecar = later upgrade path, never a v1 requirement. **Receiver =
the ecosystem observability gateway** (4317 gRPC / 4318 HTTP, ingest-key
header; exporters default to OTLP/HTTP). Exactly one product hosts that
receiver for the whole ecosystem — see "Shared ecosystem services" in the
engineering skill's `organization-policy.md`; every other product exports to
it through configuration only and never runs its own receiver. Export is
env-gated: no `OTEL_EXPORTER_OTLP_ENDPOINT` → SDK no-ops. JSON stdout logging
remains alongside (Cloud Run native). Operational telemetry ≠ product
analytics events (the shared `/v1/events` API) — separate pipelines, never
mixed. Env: `OTEL_SERVICE_NAME`, `OTEL_EXPORTER_OTLP_ENDPOINT`,
`OTEL_EXPORTER_OTLP_HEADERS`, `OTEL_RESOURCE_ATTRIBUTES`.

## Environment-variable naming standard

These names are canonical across CueLABS and Cuesoft repos and identical in
`cuesoft-delivery-standard`. Doppler `<project>/stg` is the source of values;
`.env.example` documents names with dev-safe defaults. OpenTelemetry names are
listed above.

| Variable                                                                      | Purpose                                                                                                                                           |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `APP_ENV`                                                                     | `development`, `test`, `staging` or `production`; app logic reads this, never `NODE_ENV`                                                          |
| `PORT`                                                                        | HTTP listen port; never `HTTP_ADDR` or `APP_PORT`                                                                                                 |
| `LOG_LEVEL`                                                                   | Server log level                                                                                                                                  |
| `PUBLIC_URL`                                                                  | This service's own public base URL                                                                                                                |
| `WEB_URL`                                                                     | Client origin used in links, emails and redirects; never `FRONTEND_URL` or `BASE_URL`                                                             |
| `CORS_ORIGINS`                                                                | Comma-separated exact origins, the only CORS var; no `*` default, never `ALLOWED_ORIGINS` or `CORS_ORIGIN`                                        |
| `DATABASE_URL` / `DATABASE_POOL_MAX`                                          | Postgres DSN with `sslmode`, and pool size; never discrete `DB_*` or `POSTGRES_*`                                                                 |
| `MONGO_URI` / `MONGO_DB`                                                      | Firestore (MongoDB compatibility) or MongoDB; never `MONGO_URL`                                                                                   |
| `REDIS_HOST` / `PORT` / `USERNAME` / `PASSWORD` / `TLS` / `DB` / `KEY_PREFIX` | Discrete Redis fields; never `REDIS_URL`                                                                                                          |
| `KAFKA_BROKERS` / `USERNAME` / `PASSWORD` / `SSL_CA`                          | Kafka SASL over TLS, identical in every language client; `KAFKA_SSL_CA` is PEM content                                                            |
| `GOOGLE_CLOUD_PROJECT`                                                        | GCP project id for ADC and Firebase; never `FIREBASE_PROJECT_ID` at runtime                                                                       |
| `STORAGE_DRIVER` / `BUCKET` / `PREFIX`                                        | Object storage: `gcs`, `s3` or `local`, a bare bucket name with no `gs://`; never `GCS_BUCKET`, `GOOGLE_STORAGE_URL` or `FIREBASE_STORAGE_BUCKET` |
| `STORAGE_LOCAL_PATH`                                                          | Directory for the `local` driver                                                                                                                  |
| `STORAGE_ENDPOINT` / `ACCESS_KEY` / `SECRET_KEY` / `USE_SSL`                  | The `s3` driver (MinIO locally)                                                                                                                   |
| `JWT_SECRET`, or `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY`                         | Access-token signing, symmetric or asymmetric                                                                                                     |
| `JWT_REFRESH_SECRET` / `JWT_ACCESS_TTL` / `JWT_REFRESH_TTL`                   | Refresh signing and token lifetimes as duration strings (`15m`, `720h`)                                                                           |
| `SESSION_SECRET` / `SESSION_COOKIE_NAME`                                      | Server-side sessions                                                                                                                              |
| `GOOGLE_CLIENT_ID` / `SECRET` / `REDIRECT_URI`                                | Google OAuth                                                                                                                                      |
| `BREVO_API_KEY` / `BREVO_FROM_EMAIL` / `BREVO_FROM_NAME`                      | Transactional email (REST, not SMTP)                                                                                                              |
| `PAYSTACK_SECRET_KEY` / `PAYSTACK_PUBLIC_KEY`                                 | Payments; the secret key also verifies webhooks                                                                                                   |
| `SCHEDULER_AUDIENCE` / `SCHEDULER_INVOKER_EMAIL`                              | OIDC check on `/internal/jobs/<name>` calls from Cloud Scheduler                                                                                  |
| `SERVICE_TOKEN_HASH`                                                          | Server side of service-to-service token validation                                                                                                |
| `<TARGET>_URL` / `<TARGET>_GRPC_ADDR`                                         | Base URL or gRPC address of a service this one calls                                                                                              |
| `WAKE_<TARGET>_URL`                                                           | Base URL of a consumer this service wakes; unset means always running                                                                             |
| `<FEATURE>_ENABLED`                                                           | `true` or `false`; unset means the default in code                                                                                                |
| `AIVEN_API_TOKEN` / `AIVEN_PROJECT` / `AIVEN_KAFKA_SERVICE`                   | The shared bus's keep-alive sweep only                                                                                                            |
| `DD_*`                                                                        | Exactly as Datadog defines them (`DD_ENV`, `DD_SERVICE`, `DD_VERSION`, `DD_GIT_COMMIT_SHA`)                                                       |

Naming rules:

- Name a variable after the dependency (`DATABASE_`, `REDIS_`, `STORAGE_`); a vendor prefix only for that vendor's own API (`BREVO_`, `PAYSTACK_`, `AIVEN_`).
- No app or environment prefixes (`APPARULE_`, `STG_`): the Doppler project and config carry them.
- Lists are plural and comma-separated; booleans are `true` or `false`; durations are strings such as `15m`.
- Secret names end in `_SECRET`, `_PASSWORD`, `_KEY` or `_TOKEN`.
- Browser values use `NEXT_PUBLIC_` or `VITE_` and are never secret.
- A missing required variable fails boot with every missing name listed; a missing optional variable turns its feature off.

The CORS behaviour contract
lives in each repo's engineering.md ("CORS contract" section).
