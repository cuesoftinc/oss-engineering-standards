---
name: cuelabs-engineering-standards
description: Audit, bootstrap, standardize, or verify a CueLABS repository. Use for repository structure, service naming, community-health files, project manifests, shared templates, cross-repository parity, or adoption of the CueLABS engineering standard. Route web, Flutter, design, CI, packaging, and deployment work to the focused CueLABS skills when installed.
---

# CueLABS Engineering Standards

Apply the CueLABS standard without inventing product state or deleting working
application code. Treat the target repository as the source of truth for what
exists and its `.cuelabs/project.yaml` manifest as the source of truth for what
is active, planned, or intentionally absent.

## Select the operation

- **Audit**: inspect without changing files and report conformance, deviations,
  and unknowns.
- **Plan**: produce an ordered change plan and explicit assumptions without
  changing files.
- **Apply**: make the requested standardization changes, then verify them.
- **Bootstrap**: start a new product with the bundled script's `init`
  operation, then create only the surfaces the user requested; never create
  empty application placeholders. Follow "Procedure B" in
  `references/repository-and-services.md`. Before running `init`, ask the
  user for anything they have not given: the product slug (you may suggest
  one from the directory name), display name, profile, and each surface's
  status. Before filling a product decision, propose a value with a one-line
  reason and wait for the user's answer.
- **Verify**: run deterministic checks and report evidence.

Default to **audit** for review requests. Use **apply** only when the user asks
to change, fix, bootstrap, or standardize the repository.

## Read the relevant resources

- Read [references/repository-and-services.md](references/repository-and-services.md)
  for repository layout, service naming, community files, bootstrap, cleanup,
  and language conventions.
- Read [references/organization-policy.md](references/organization-policy.md)
  for CueLABS identity, API, documentation, data, telemetry, and environment
  policy.
- Read [references/project-manifest.md](references/project-manifest.md) before
  authoring or repairing `.cuelabs/project.yaml`.
- Read [references/product-decisions.md](references/product-decisions.md)
  when bootstrapping a product or auditing whether its per-product values
  (slug, default theme, ports, data store, and so on) are recorded.
- Read [references/qa-and-orchestration.md](references/qa-and-orchestration.md)
  when coordinating multiple repositories or closing a QA/merge loop.
- Read [references/recommended-versions.md](references/recommended-versions.md)
  only when selecting or aligning toolchain versions; verify unstable versions
  from their primary sources before changing them.
- Use `assets/profiles/base.yaml` for portable OSS defaults and
  `assets/profiles/cuelabs.yaml` for CueLABS-specific policy.
- Validate `.cuelabs/project.yaml` against
  `assets/schema/project.schema.json`.
- Use `assets/templates/` as the source for profile-managed repository files.
  For `base`, preserve repository-authored ownership, licensing,
  community-health, and application files; do not substitute CueLABS identity.

For a focused surface, activate the matching installed skill:

- `$cuelabs-web-standard`
- `$cuelabs-mobile-standard`
- `$cuelabs-design-standard`
- `$cuelabs-delivery-standard`
- `$cuelabs-system-design` (whole-system design, service breakdown, and
  architecture diagrams)

Do not duplicate a focused skill's full guidance into the working context
unless the task actually touches that surface.

## Workflow

1. Inspect repository instructions, status, manifests, documentation, and real
   source directories.
2. Read `.cuelabs/project.yaml` when present. If absent, infer current surfaces
   from evidence and label the inference; do not treat a roadmap as built code.
3. Classify each surface as `active`, `planned`, `paused`, or `absent`.
4. Resolve this installed skill's directory from the active skill metadata or
   path, then run its bundled script by absolute path:

   ```bash
   python3 <skill-dir>/scripts/cuelabs_standard.py audit --repo <target-repo>
   ```

   Use `--format json` when another tool will consume the result.
5. Separate findings into:
   - portable base-standard failures;
   - CueLABS-profile failures;
   - product-specific decisions;
   - intentional, documented deviations;
   - unknowns requiring product direction.
6. For apply work, show or inspect the plan first:

   ```bash
   python3 <skill-dir>/scripts/cuelabs_standard.py plan --repo <target-repo>
   ```

7. Preserve application code and git history. Use `git mv` for structural
   moves. Copy a template only when its destination is missing unless the user
   explicitly approves replacement.
8. Update documentation and `.cuelabs/project.yaml` in the same change when the
   repository's declared state changes.
9. Run repository-native tests plus:

   ```bash
   python3 <skill-dir>/scripts/cuelabs_standard.py verify --repo <target-repo>
   ```

10. Report changed files, checks, remaining deviations, and any decisions that
    still belong to the user.

## Non-negotiable safeguards

- Never scaffold a backend, mobile app, deployment, or CI job merely because it
  is planned.
- Never delete application code, models, fixtures, or assets as
  "standardization."
- Never overwrite a repository-specific README, changelog, Dependabot manifest,
  or project manifest with a shared template.
- Never present product-specific policy as a portable OSS requirement.
- Never silently resolve an explicit documented deviation.
- Never record a product decision (`P-nn` value) or manifest identity the user
  has not confirmed; leave it `—` and list it as an open decision.
- Keep shared files byte-identical only when the standard marks them shared;
  keep product variation in manifests, scripts, or documented extension points.

## Result format

For audits and plans, return:

1. detected profile and surfaces;
2. conforming areas;
3. deviations grouped by severity;
4. proposed actions with affected paths;
5. assumptions and unresolved product decisions;
6. verification commands.
