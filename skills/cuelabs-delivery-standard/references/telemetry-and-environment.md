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

Identical names across all repos (Doppler `<project>/stg` is the source of
values; `.env.example` documents names with dev-safe defaults):
`PORT` · `CORS_ORIGINS` (comma-separated exact origins — the only CORS var;
never ALLOWED_ORIGINS/FRONTEND_URL) · `REDIS_HOST/PORT/USERNAME/PASSWORD/TLS/DB`
(discrete, never a single URL) · `BREVO_API_KEY/FROM_EMAIL/FROM_NAME` ·
`GOOGLE_CLOUD_PROJECT` · `SERVICE_TOKEN_HASH` (server side of s2s token
validation) · DB: `DATABASE_URL` (Postgres) / ADC for Firestore
(`MONGO_URI`+`MONGO_DB` only in repos still on MongoDB) ·
`KAFKA_BROKERS`/`KAFKA_USERNAME`/`KAFKA_PASSWORD`/`KAFKA_SSL_CA` (Aiven Kafka
pub/sub, identical names in every language client). CORS behaviour contract
lives in each repo's engineering.md ("CORS contract" section).
