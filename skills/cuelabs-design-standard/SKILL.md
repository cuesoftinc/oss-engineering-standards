---
name: cuelabs-design-standard
description: Create, audit, or standardize CueLABS product design systems and their implementation contracts. Use for Figma variables, tokens, component libraries, screen states, prototype flows, accessibility and motion specifications, design documentation, visual QA, or cross-product design parity.
---

# CueLABS Design Standard

Maintain design artifacts as implementation contracts. Preserve each product's
visual identity while keeping shared foundations, naming, accessibility, and QA
methods consistent.

## Read the relevant references

- Read [references/figma-and-design.md](references/figma-and-design.md) for
  design documentation, variables, components, states, prototype wiring,
  content integrity, and Figma-specific constraints.
- Use the "Design QA loop" rule in `figma-and-design.md` when planning or
  closing audit/fix/re-verify rounds. For multi-agent orchestration and merge
  gates, activate `$cuelabs-engineering-standards` when installed.

## Workflow

1. Inspect product decisions, design documentation, current code, and the
   actual design file before changing either side.
2. Determine whether the task affects foundations, components, screens,
   content, flows, accessibility, motion, or parity.
3. Keep product tokens in true light/dark modes and pair accent fills with
   explicit on-accent text tokens.
4. Build screens from live component instances and include required default,
   empty, loading, error, and destructive states where the product contract
   calls for them.
5. Keep implementation notes in component descriptions or documentation, not
   visible product canvases.
6. Wire and verify named prototype flows. Prove core-flow reachability and
   eliminate unintended dead ends.
7. Run independent completeness, content, accessibility, and polish passes.
   Record findings with stable node or file identifiers and severity.
8. Verify each fix against the artifact and update the implementation contract
   when a design decision changes.

## Guardrails

- Do not fabricate customer claims, usage numbers, pricing, research results,
  or third-party endorsements.
- Do not ship a screen that lacks its required states.
- Do not represent dark mode as component variants when token modes are the
  governing mechanism.
- Do not treat screenshots as a substitute for inspectable tokens and
  components.
- Do not mark a QA finding resolved based only on the builder's statement.
- Do not force a shared visual style where the standard requires only shared
  structure or behavior.

## Result format

Report artifacts inspected, shared and product-specific decisions, nodes or
components changed, QA findings and dispositions, accessibility checks, and
implementation follow-ups.
