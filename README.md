# CueLABS™ Engineering Standards

An opinionated, versioned, cross-agent engineering standard for CueLABS™
projects and compatible open-source teams.

This repository is a catalog of portable [Agent Skills](https://agentskills.io/)
plus deterministic templates and validation tools. It works with Codex, Cursor,
GitHub Copilot, Claude Code, and other clients supported by GitHub CLI.

## Skill catalog

| Skill | Use it for |
|---|---|
| `cuelabs-engineering-standards` | Repository audits, bootstrapping, structure, shared files, manifests, and cross-repository parity |
| `cuelabs-web-standard` | Next.js, React, TEST_MODE, components, accessibility, performance, SEO, and marketing parity |
| `cuelabs-mobile-standard` | Flutter architecture, Riverpod, fakes, flavors, goldens, platform builds, and mobile parity |
| `cuelabs-delivery-standard` | GitHub Actions, containers, Helm, Terraform, telemetry, releases, and deployment readiness |
| `cuelabs-design-standard` | Figma variables, design systems, components, prototypes, accessibility, and visual QA |
| `cuelabs-system-design` | System designs from a PRD, a repository, or a description: services, communication, data ownership, and a diagram page with Excalidraw and Mermaid copy buttons |

The repository root intentionally has no `SKILL.md`. Installable skills live
under `skills/<skill-name>/SKILL.md`, which allows clients to discover,
validate, install, and update them independently.

## Install

GitHub CLI 2.96 or newer includes the preview `gh skill` commands used below.

Install every skill globally for Codex:

```bash
gh skill install cuesoftinc/oss-engineering-standards \
  --all \
  --agent codex \
  --scope user
```

Install every skill globally for Cursor:

```bash
gh skill install cuesoftinc/oss-engineering-standards \
  --all \
  --agent cursor \
  --scope user
```

Install one skill:

```bash
gh skill install cuesoftinc/oss-engineering-standards \
  cuelabs-web-standard \
  --agent cursor \
  --scope user
```

Install into the current repository:

```bash
gh skill install cuesoftinc/oss-engineering-standards \
  --all \
  --agent codex \
  --scope project
```

Codex and Cursor resolve compatible project installations to
`.agents/skills/`, so one committed project installation can serve both.

Pin a release for reproducible project behavior:

```bash
gh skill install cuesoftinc/oss-engineering-standards \
  --all \
  --agent codex \
  --scope project \
  --pin v2.0.0
```

Update tracked installations:

```bash
gh skill update --all
```

See [adoption](docs/adoption.md) for team installation patterns and
[compatibility](docs/compatibility.md) for supported clients.

## Use

Skills trigger automatically from their descriptions. They can also be invoked
explicitly:

```text
Use $cuelabs-engineering-standards to audit this repository.
Use $cuelabs-delivery-standard to standardize GitHub Actions.
Use $cuelabs-web-standard to review this dashboard against CueLABS conventions.
Use $cuelabs-system-design to design this product's backend from its PRD.
```

The primary skill also includes a dependency-free terminal tool:

```bash
python3 skills/cuelabs-engineering-standards/scripts/cuelabs_standard.py \
  audit --repo /path/to/repository
```

Available operations are `init`, `audit`, `plan`, `apply`, and `verify`.
`init` starts a new product: it writes `.cuelabs/project.yaml` and a
`docs/decisions.md` seeded with the product parameters to decide. `apply`
copies only missing profile-managed files. Neither overwrites existing files
or writes through symlinked paths.

Start a brand-new product:

```bash
git init acme && cd acme
printf '# Acme\n' > README.md && printf '# Changelog\n' > CHANGELOG.md
python3 <skill-dir>/scripts/cuelabs_standard.py init --repo . \
  --name acme --surface web=planned
python3 <skill-dir>/scripts/cuelabs_standard.py apply --repo .
```

## Profiles and project state

- `base` contains portable open-source engineering defaults.
- `cuelabs` layers CueLABS™ identity, platform, delivery, and observability
  decisions over the base.
- The portable profile manages only neutral shared defaults automatically.
  Ownership, licensing, community-health, and application files remain
  repository-authored and are checked for presence without enforcing CueLABS
  content.
- Each product owns its current state in `.cuelabs/project.yaml`; the standards
  repository defines the schema, not whether a product backend or mobile app is
  currently ready.
- Manifests use the documented
  [dependency-free YAML subset](skills/cuelabs-engineering-standards/references/project-manifest.md);
  the schema validates data shape rather than expanding the accepted syntax.

The example and JSON Schema live under
`skills/cuelabs-engineering-standards/assets/`.

## Repository structure

```text
skills/                    Installable, self-contained Agent Skills
evals/                     Trigger and routing evaluation cases
scripts/                   Catalog validation
docs/                      Human-facing adoption and governance
.github/workflows/         Catalog validation
```

## Validate

```bash
python3 scripts/validate_catalog.py
gh skill publish --dry-run
```

The first command is dependency-free and validates local structure, links,
metadata, line limits, and evaluation coverage. The second runs GitHub's
official Agent Skills and repository checks without publishing.

Run the baseline CLI regression suite with:

```bash
python3 -m unittest discover -s tests -v
```

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and
[governance](docs/governance.md). Standards changes must explain affected
profiles and projects, include migration guidance for breaking behavior, and
keep all catalog checks green.

## License

[MIT](LICENSE)
