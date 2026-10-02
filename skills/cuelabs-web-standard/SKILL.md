---
name: cuelabs-web-standard
description: Build, audit, or standardize CueLABS web applications and marketing sites. Use for Next.js and React architecture, design tokens, component libraries, TEST_MODE, mock APIs, routes, accessibility, performance, SEO, marketing navigation and footer parity, or Figma-to-web implementation.
---

# CueLABS Web Standard

This standard covers CueLABS open-source product repositories (`web/` tree). The
cuelabs.cuesoft.io division site is a Cuesoft site and follows
`cuesoft-web-standard`; these rules do not apply to it.

Implement the web surface from the product's current documentation and design
artifacts. Preserve product character while enforcing shared engineering,
accessibility, testing, and integration contracts.

## Read the relevant references

- Read [references/web-implementation.md](references/web-implementation.md)
  for architecture, tokens, MVC boundaries, routes, TEST_MODE, mocks, testing,
  accessibility, and implementation rules.
- Read [references/web-tooling.md](references/web-tooling.md) for package
  scripts, linting, formatting, Vitest, Playwright, Tailwind, Next.js config,
  performance, SEO, and parity files.
- Read [references/marketing-parity.md](references/marketing-parity.md) only
  when touching marketing navigation, footer, themes, public links, or shared
  CueLABS copy.

## Workflow

1. Inspect repository instructions, `.cuelabs/project.yaml`, product docs,
   source, tests, and the referenced design artifact.
2. Confirm the web surface is `active`. If it is `planned`, stop at design or
   planning unless the user explicitly asks to begin implementation.
3. Determine the task layer:
   - foundations and tokens;
   - UI components;
   - public marketing;
   - dashboard/application routes;
   - models/controllers/network boundaries;
   - testing/tooling;
   - accessibility/performance/SEO.
4. Read only the references needed for those layers.
5. Reuse existing product components and tokens. Do not replace product design
   with a generic component kit.
6. Keep views render-only, controllers responsible for orchestration, and
   models/repositories responsible for network access.
7. Keep TEST_MODE behavior behind the standard provider and mock seams. Do not
   introduce production authentication merely to satisfy a web-only phase.
8. Add or update unit, integration, and Playwright coverage for changed
   behavior.
9. Verify with the repository's lint, typecheck, unit, build, and relevant e2e
   commands. Compare rendered output to the current design source when visual
   fidelity is in scope.

## Guardrails

- Do not invent backend endpoints, pricing, metrics, customer claims, or product
  state.
- Do not add legacy redirects unless the product contract explicitly requires
  them.
- Do not use raw colors when a token exists.
- Do not fetch from views.
- Do not ship enabled controls without behavior.
- Do not let overlays, tables, charts, or navigation create document-level
  overflow at supported viewports.
- Do not trade accessibility or reduced-motion behavior for visual fidelity.

## Result format

Report the product contracts consulted, layers changed, parity decisions,
verification evidence, visual checks, and remaining backend or design
dependencies.
