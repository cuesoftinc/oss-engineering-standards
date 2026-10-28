## Recommended versions
Keep current; last reviewed with the values below.

| Area | Version |
|------|---------|
| Next.js / React / TypeScript | 16.x / 19.2 / 5.9 |
| Go | 1.26 fleet-wide (single-truth canon) — builder image matches the module's `go` directive (`golang:1.26-alpine`) |
| Gin | v1.12 |
| Node | 24 (`node:24-slim` images) |
| NestJS (Node API services, `api/<service>`) | 11.x — same TypeScript 5.x floor as `web` |
| Android (Kotlin / Gradle / compileSdk) | 2.2 / 9.1 / 36 — for future native apps |
| Python | 3.12 (`python:3.12-slim` images) |

Pin exact versions in each service's manifest; let Dependabot (scoped, grouped)
propose upgrades.
