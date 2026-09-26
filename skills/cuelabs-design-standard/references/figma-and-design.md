# Figma and design-system standard

## Design documentation standard

Each repo's `design.md` defines: reference feel, color tokens (mirrored as
Figma variables in `<product>/tokens` with **true Light/Dark modes**; plus
foundations variables — spacing, radii, durations, z-index — in the same
collection), type scale,
layout, component inventory, a numbered microinteraction catalog (`MI-n`,
referenced from pages.md), accessibility/motion rules, and the **shared
foundations block** — spacing scale (4px grid: 4/8/12/16/24/32/48/64),
breakpoints (640/768/1024/1280/1536), motion durations (120/200/250/300ms) +
easings, z-index layers (0/10/20/30/40/50), **Lucide** icons, focus ring
(2px accent, offset 2, :focus-visible). The foundations rows are identical
across products — changing one is an ecosystem PR touching every product.

**Docs describe the current system**: design docs are a snapshot of what
is on `main` now, not a changelog; git history and PRs are the changelog.

### Figma component-library standard

How each product's Figma library is built:

- **Token pairing** — every accent/brand fill token pairs with an
  `on-accent`/`on-brand` color token for the ink rendered on it. Raw hex is
  allowed **only** for documented exceptions: on-media camera UI, gradient
  stops (Figma cannot bind variables to them), effect/shadow colors, and
  crit-fill labels pending an `on-crit` token.
- **Theme delivery** — dark mode ships as **true Light/Dark variable modes**
  on `<product>/tokens`, never as `theme` variant axes on components.
  Both-mode QA preview frames with **live instances** are mandatory.
- **Library organization** — the Components page holds an "About" README
  card + stage frames in one left-aligned column (240px gaps), with QA
  frames in a parallel right column. File page order: Style Guide →
  Components → (Assets) → surfaces → Deprecated. Run a zero-overlap check
  before shipping.
- **Naming** — PascalCase component sets; lowercase variant properties
  (`kind`, `size`, `state`, …); icons `icon/<lucide-slug>`, brand glyphs
  `icon/brand-<name>` (brand marks keep their official colors, unbound).
  The ecosystem auth CTA component is **`GoogleAuthButton`** (Google-only
  sign-in).
- **Engineering practices** — auto-layout everywhere; every color
  variable-bound; tint overlays are instance-safe rects using **node-level**
  opacity (Figma drops paint-level opacity on variable-bound instance
  fills); component descriptions carry the MI/motion notes and **[Decided]**
  mappings that apply to them; OpenType tabular figures (`tnum`) must be
  toggled manually — the plugin API cannot set font features. Two more
  API gotchas: the `description` write path HTML-escapes
  quotes/angle-brackets/ampersands at storage (write entity-safe —
  typographic quotes, no `<` or `&`), and page enumeration must use a
  read-only `figma.root.children` call (the no-nodeId listing returns
  only loaded pages).
- **Content** — photography must be licensed, with attributions rendered on
  the Assets page; screens assemble from component instances **only**.
- **Canvas hygiene** — design canvases carry **product copy only**; spec
  annotations (MI references, requirement IDs, implementation notes) belong
  in component descriptions and the docs, never inside screen frames.
- **Design accuracy** — marketing/design surfaces carry **no fabricated
  third-party statistics** (GitHub stars, member/user/download counts), no
  invented pricing or plan claims (until pricing is decided the only
  permitted lines are "self-hosting is free forever" / "cloud pricing
  announced at GA"), no invented SLAs or research statistics, and no
  implied customer endorsements. Product claims are framed as
  targets/capabilities ("we target ±2 cm"), demo data is clearly synthetic,
  and license claims match the repo `LICENSE` (CueLABS™ products: MIT).
  GitHub badges render as glyph + "Star" with **no count**.
- **Screen states** — every data-driven screen template ships **default +
  empty + loading** frames: empty uses the `EmptyState` component with real
  first-run copy (plus a demo-data toggle where the product specs one);
  loading uses `Skeleton` primitives.
- **Prototyping standard** — core journeys are wired as **named flow
  starting points** per page. Conventions: `ON_CLICK` → `NAVIGATE`;
  `DISSOLVE` 150-200ms for nav/tab switches; `SMART_ANIMATE` for
  pushes/backs; `AFTER_TIMEOUT` for async verification states.
  Empty/loading/QA/index frames stay out of the flow. Reachability is
  proven by BFS over the reaction graph — no unreachable core screens, no
  dead ends besides terminals. Cross-page links use the
  **move-wire-restore** technique: the API rejects creating cross-page
  `NAVIGATE`, but reactions persist when the source frame is temporarily
  moved to the destination page, wired, and returned.
- **Design QA loop** — before design sign-off, run audit → fix → re-verify
  rounds to convergence with **independent auditors** (not the builders)
  across three lenses: **completeness** (docs contract + states +
  prototype graph), **content** (wording, geometry on the 4px scale,
  placement, and data coherence — one narrative across screens: dates,
  ledgers, registries, role perspectives), and **polish** (mode flips,
  contrast, stray objects, rhythm). Findings carry node ids + severities;
  fixes are verified per-item against the finding ledger in the next
  round.
