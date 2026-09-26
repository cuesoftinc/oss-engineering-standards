---
name: cuelabs-delivery-standard
description: Audit, create, or standardize CueLABS delivery systems. Use for GitHub Actions, CI parity, release workflows, Dockerfiles, Docker Compose, Helm, Terraform, Cloud Run, Firebase App Hosting, environment variables, OpenTelemetry, artifacts, or deployment readiness.
---

# CueLABS Delivery Standard

Standardize delivery around the repository's real, build-ready surfaces. Keep
CI uniform without creating jobs for backends, mobile apps, or deploy targets
that do not exist yet.

## Read the relevant references

- Read [references/cloud-and-ci.md](references/cloud-and-ci.md) for CueLABS
  cloud policy, GitHub Actions, release gating, versions, and fleet parity.
- Read [references/containers-and-deploy.md](references/containers-and-deploy.md)
  for Docker, Compose, ports, Helm, and Terraform.
- Read
  [references/telemetry-and-environment.md](references/telemetry-and-environment.md)
  for OpenTelemetry and environment-variable conventions.

## Workflow

1. Inspect `.cuelabs/project.yaml`, real manifests, workflows, build scripts,
   container files, deploy definitions, and repository documentation.
2. Classify every surface as build-ready or not build-ready from executable
   evidence, not roadmap text.
3. Build a job matrix from build-ready surfaces only.
4. Compare shared jobs with the current CueLABS canonical shape. Keep
   repository variation in package/build scripts rather than duplicated
   workflow logic.
5. Verify current official action versions from their primary release sources
   whenever a workflow is changed.
6. Apply least-privilege permissions, concurrency cancellation, named steps,
   deterministic dependency installation, and failure artifact retention.
7. Keep website rollout, API release, and self-host deployment paths distinct.
8. Validate every changed layer with the native tool:
   - workflow syntax and repository checks;
   - container build or configuration validation;
   - `helm lint` and `helm template`;
   - Terraform formatting and validation;
   - service health/readiness behavior.

## Guardrails

- Do not add an API or mobile CI job before that surface is build-ready.
- Do not deploy from a pull request.
- Do not add a release workflow before the deployment phase is approved.
- Do not grant broad `GITHUB_TOKEN` permissions by default.
- Do not introduce a second environment-variable name for an existing
  cross-repository concept.
- Do not embed secrets in workflows, images, manifests, examples, or logs.
- Do not claim a deployment succeeded without checking its terminal state.

## Result format

Report detected surfaces, included and deferred jobs, parity differences,
security decisions, validation evidence, and deployment actions that remain
deliberately unperformed.
