# Web implementation standard

## Contents

- Stack, tokens, components, and MVC
- Source-tree and library conventions
- Layout, markup, overlays, charts, and responsive behavior
- Routes, naming, settings, dates, and TEST_MODE
- Mocks, tests, quarantine, reuse, and delivery stages

## Canon

How each product's `web/` app is built. Values marked *(product decision)*
are chosen once per product and recorded in its `docs/decisions.md` — see the
engineering skill's `product-decisions.md`.

- **Stack** — Next.js 16 App Router + React 19 + TypeScript; Tailwind
  utilities map to the token CSS variables. Components are
  token/Tailwind-based everywhere.
- **Design tokens** — `web/src/design/tokens.css` holds CSS custom
  properties mirroring `design.md`'s token section exactly: colors as light
  `:root` / dark `[data-theme="dark"]` (honoring `prefers-color-scheme` with
  manual override), spacing 4–64, radii, durations + easings, z-index layers,
  the series palette where the product has one, and on-accent/on-brand inks.
  **No raw hex in components** — the same rule as Figma; documented
  exceptions carry a code comment.
- **Components** — `web/src/components/ui/<Name>.tsx`: one module per Figma
  component set, named exactly as the set (PascalCase); props mirror the
  variant axes (`kind`/`size`/`state`/…); `design.md`'s microinteractions
  are implemented with duration/easing tokens and `prefers-reduced-motion`
  fallbacks; every component is unit-tested.
- **MVC layering** — models = `src/models/` (typed entities per
  data-model.md + repositories per api.md/openapi.yaml — the **only** layer
  that talks to the network); controllers = `src/controllers/`
  (feature-scoped hooks/orchestration that own all state); views =
  `src/app/**` routes + composed components, render-only. **Views never
  fetch.**
- **Canonical `web/src/` tree** — exactly:
  `app, auth, components, config, controllers, design, generated, lib,
  mocks, models` (+ documented product-specific dirs, e.g. `proto/` for a
  product with generated protocol clients). `mocks` is PLURAL; auth
  providers/context live in `src/auth/` (not under controllers); env access
  goes through `config/env.ts` typed accessors only; shared utils in `lib/`;
  **no top-level modules in `src/`**. Tree SHAPE is a parity item:
  standardization sweeps diff the directory trees across repos, not just
  file contents/tooling — comparing contents alone lets shape drift survive.
- **Canonical libraries (uniform across products)** — interactive/behavior
  primitives use **Radix UI** (`@radix-ui/react-*`: dialog, popover, select,
  switch, tooltip, tabs, checkbox, radio, accordion); positioning-only cases
  may use Floating UI; the date library is **date-fns** (never dayjs/moment
  in new code); class composition via `clsx`; icons via `lucide-react` +
  inline brand SVGs. All behavior-bearing overlays ride Radix; a bespoke
  layer is allowed only when it is positioning- or layout-class (per the
  floating-layers measure-and-clamp clause below) and is recorded in the
  product's `web-implementation.md`.
- **Layout & markup canon (uniform across products)** — every
  marketing/app page constrains content to ONE centered container per the
  product's `design.md` layout spec (full-bleed is for band BACKGROUNDS
  only; section inner content always aligns to the container — measured by
  rect, not eyeballed). Semantic HTML is required: exactly one `<main>`
  per page; `nav`/`header`/`footer`/`section`/`aside` landmarks; heading
  hierarchy; `ul/li` lists; real `table` semantics for tabular data;
  `button` vs `a` used correctly — div-soup is a review failure. No
  UNLAYERED element selectors (`main{}`, `button{}`, `svg{}`…) outside
  `@layer base` — an unlayered `main{min-width:100vw}` breaks layout
  (min-width beats max-width); element rules live in layers so utilities
  win. Circular imagery (avatars, story rings) is aspect-locked +
  cover-cropped (`aspect-square object-cover rounded-full`) at the
  component level.
  - **Cursor affordance**: enabled interactive controls show
    `cursor: pointer` via ONE base-layer rule —
    `button:not(:disabled), [role="button"]:not([aria-disabled="true"]),
    select:not(:disabled), summary, label[for] { cursor: pointer }` — links
    rely on the native pointer; disabled controls keep the default cursor.
    (Tailwind v4 preflight defaults buttons to `cursor: default`; the
    explicit rule gives v3 and v4 repos identical behavior. Clickable
    surfaces that aren't real buttons/links are a semantic-HTML violation,
    not a cursor problem.) An e2e asserts the computed cursor on a button
    and a nav link.
  - **Floating layers collision-clamp**: every popover/dropdown/menu/
    date-picker must stay fully within the viewport at every breakpoint and
    anchor position, on BOTH axes (Radix layers get
    `collisionPadding`/`align`; bespoke layers measure + clamp, and FLIP
    ABOVE the anchor when the space below can't hold them). An open layer
    NEVER creates a page scrollbar. e2e asserts an edge-anchored layer's
    boundingBox is inside the viewport at 1440 and 390, plus a SHORT
    viewport (~1440×700) for bottom-anchored pickers. ANATOMY: a new
    floating panel's internals (padding, section separation, header/grid
    spacing) are pixel-verified against its Figma master before merge —
    behavior checks alone miss cramped, edge-flush padding. GOTCHA
    (Enter-commit focus-restore): committing a layer's value via Enter must
    not restore focus to the trigger in a way that immediately reopens the
    layer — close handlers guard against reopen-on-refocus.
  - **Modal-embedded menus**: a Select/dropdown opened INSIDE a Modal/Sheet
    must not clip against the modal body's overflow into a raw inner
    scrollbox — menus portal outside the modal's scroll container (or the
    modal body exempts them from clipping) and render as proper padded
    height-capped layers.
  - **Dashboard mid-band balance**: two-column overview bands bottom-align
    per the frame — flexible plot/list heights with min-height floors
    absorb the delta; a shorter column never leaves a dead whitespace strip
    under it.
  - **Danger-affordance ladder**: destructive row-level actions render as
    QUIET danger text links — a `Button` `kind="quiet-danger"` (danger text
    on quiet chrome, mirrored by a "Button (quiet-danger)" Figma variant);
    filled danger buttons are reserved for armed/confirm surfaces;
    account/data-destroying confirms are TYPED (the product ratifies the
    confirm token, e.g. the org name) with an "Export everything first"
    escape hatch and grace-period semantics where ratified. Products without
    the kind add it before shipping a row-level destructive action.
  - **Chart construction**: bespoke charts follow their Figma master's axis
    construction — dedicated y-axis column with a nice-scale tick ladder
    (1/2/2.5/5×10^k), unit/currency-aware compact labels, token-bound
    gridlines, zero baseline where mastered; DATA HONESTY: never fabricate
    points for periods before the data exists (trim to onset), discrete
    observations (e.g. two fiscal years) render with point markers,
    series/domains never lie about granularity. GOTCHA:
    `vector-effect: non-scaling-stroke` computes DASH metrics in screen
    space, so it silently breaks any `pathLength`-normalized
    `stroke-dasharray` trick (e.g. dash draw-in animations) — on a
    stretched/`preserveAspectRatio="none"` SVG the series renders as
    literal dashes with data-hiding gaps. Never combine the two on one
    element; stretched-fill series fade in instead, and e2e pins the
    stretched polyline dash-free.
  - **Landing type fidelity**: web type binds the product's Figma FAMILY —
    the family loads via `next/font` (variable, real 400/600/700), never
    left to the OS system stack (a system fallback renders visibly heavier
    and wider, which reads as a font-weight bug when the family is the real
    cause); ramp letter-spacing lives in the theme's text tokens
    (Title/24 −0.25px, Display/32 −0.5px etc.), never inline per-element.
    Fleet smoothing pair: `-webkit-font-smoothing: antialiased` +
    `-moz-osx-font-smoothing: grayscale` (grayscale AA is how Figma
    rasterizes; `auto` reads heavier than the canvas) — via a globals
    `body` rule or Tailwind `antialiased` on `<html>`, both blessed.
    Each home.spec carries a per-role TYPE-CONTRACT e2e (computed
    family/weight/size/line-height/letter-spacing per landing role).
  - **Micro-labels**: where a product uses micro-labels (table headers,
    footer columns, section headings) they are 11px uppercase tracking-wide
    — masters and build match.
  - **Mobile-width CSS traps**: percentage `max-w-full` is ignored during
    intrinsic sizing — wide children need `grid-cols-1`/`minmax(0,…)`
    tracks and `min-w-0` on flex items; `<fieldset>` carries UA
    `min-inline-size: min-content` (defeats truncation — reset it);
    same-property Tailwind utilities (`hidden` vs a component's base
    `inline-flex`) resolve by stylesheet order, not class order — put
    responsive visibility on WRAPPER elements, never on a component that
    sets the same property. Wide tables/charts/waterfalls sit in
    `overflow-x-auto` containers scrolling within the viewport — the
    document itself never side-scrolls (e2e sweeps every route at 390
    asserting `scrollWidth <= viewport`).
  - **Expandable chrome**: products with expandable sidebars/rails verify
    the MAIN CONTENT column in BOTH rail states — no clipped or overflowing
    charts/tables/grids with the rail expanded, especially at 1024–1440
    where the expanded rail squeezes the column hardest; the e2e route
    sweep runs with the rail expanded too. **On mobile (`<md`) the
    expanded rail NEVER squeezes content**: expansion renders as an overlay
    drawer above the content with a scrim (content keeps full width
    beneath; scrim tap / Escape closes), and a desktop-persisted expanded
    state does not apply below `md` — mobile always boots with the
    collapsed rail. e2e at 390: expanding overlays (content width
    unchanged), scrim closes.
- **Canonical routes (uniform across products)** — `/` is the public home;
  `/signin` is the ONLY auth route (never `/login`/`/signup`; legacy paths
  get NO redirect stubs — once a replacement lands, old routes are deleted
  outright and 404 on the branded page); every authenticated app surface
  nests under `/dashboard/<area>` (`/dashboard` = the overview; e.g.
  `/dashboard/orders`, `/dashboard/logs`); the dev-only component gallery is
  `/dev/components` (excluded from production builds); the mock API mounts
  at `/api/mock/v1/*` mirroring `/api/v1/*` path-for-path.
- **Canonical naming (uniform across products)** — landing/marketing section
  components live in `web/src/components/home/` (one module per `pages.md`
  Part A section); the marketing chrome components are named
  **`MarketingNav`** / **`MarketingFooter`** in every repo; the analytics
  controller is a hook named **`use-analytics.ts`** exposing the `pages.md`
  event register behind a TEST_MODE-safe transport seam (events queue
  inspectably in TEST_MODE; the beacon to the shared analytics service is
  env-gated).
- **Settings IA** *(product decision: route-backed tabs or hub)* — the
  default is ROUTE-BACKED TABS: a settings-local tab bar where every tab is
  a real sub-route (`/dashboard/settings/<tab>`, deep-linkable; bare
  `/dashboard/settings` redirects to the first tab — a live-IA redirect,
  not a legacy stub). A product whose settings are a list of sub-screens
  may instead use a HUB with sub-screen rows. Either shape is a designed
  decision recorded in `docs/decisions.md`, not drift.
- **Date idiom** *(product decision)* — each product picks ONE idiom per
  surface class and records it in `design.md`: finance/audit surfaces render
  ABSOLUTE dates; social/feed surfaces render RELATIVE phrasing
  (`formatAgoPhrase`); telemetry surfaces render absolute UTC-derived stamps
  with `MMM d` for pre-today. Mixed idioms on one surface are a review
  failure.
- **TEST_MODE contract** — `NEXT_PUBLIC_TEST_MODE=1` makes
  `GoogleAuthButton` navigate straight to the dashboard (no Firebase) and
  points the API client at the in-app mock server. Auth sits behind an
  `AuthProvider` interface (`TestModeAuthProvider` now;
  `FirebaseAuthProvider` added at backend-integration time — Google-only
  either way).
- **Mock server** — Next route handlers under `src/app/api/mock/*`
  implement the documented API surface the web needs (paths, snake_case
  error codes, and taxonomies from api.md/openapi.yaml), backed by a seeded
  in-memory store with full CRUD (dev-persistent via a module singleton).
  Seed data reproduces the docs/Figma mock narratives so the app boots
  looking like the designs; contract types are shared with models.
- **Tests** — Vitest + Testing Library for unit/integration (components,
  controllers, mock handlers); Playwright e2e mirrors `design.md`'s
  prototype journeys, run in TEST_MODE against the mock server. Both wire
  into CI build+test (Actions never deploys — though the websites ride
  Firebase App Hosting auto-rollouts from `main`, so a green merge IS
  user-visible within the hour).
- **Legacy / dead-code quarantine** — before replacement, legacy trees are
  `git mv`-ed into `web/src/legacy/` (structure preserved, excluded from
  build & routing); live paths carry **zero dead code**. Once the
  replacement passes QA + Playwright, the legacy subtree is deleted in a
  dedicated `chore(web): retire legacy <area>` PR. No dead code outside
  `src/legacy/`, ever; a repo carries `src/legacy/` only while a
  deprecation is in flight. The retirement PR also rewrites any docs that
  referenced the removed content so the docs describe only the current
  system (the quarantine guardrails — eslint boundary rules +
  check-boundaries — stay in place to police future quarantines).
- **Component reuse policy** — pixel-fidelity to the Figma files wins: all
  **visual** components are built in-house from the token layer — no styled
  component kits in new code (no new MUI, no shadcn/DaisyUI skins) and no
  chart libraries (charts are bespoke SVG built to the Figma chart specs).
  Reuse is allowed only where it is invisible: headless behavior primitives
  (Radix/Base UI class — dialog, popover, select, tabs, switch, checkbox,
  tooltip, accordion semantics with focus traps, keyboard nav, ARIA),
  positioning engines (Floating UI), **lucide-react** (the design system's
  own icon set — matches by construction; brand glyphs as local SVGs), and
  math/format utilities (d3-scale, date-fns, clsx). Fidelity is verified
  against the Figma files in the stage QA loops (screenshot comparison +
  token/geometry checks).
- **Process** — stages W0 foundations → W1 components → W2 home → W3
  dashboards, one PR per stage per repo; conventional commits; a stage
  closes only after its QA loop evaluates the implementation against the
  Figma files (tokens, geometry, states, interactions). Docs + this
  standard are updated with every deviation.
