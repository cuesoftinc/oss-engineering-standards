# Product decisions

The standard fixes rules; each product fixes a small set of values the rules
leave open. This file lists every such value so a new product can decide them
up front and an audit can check they are recorded.

## Where values live

- **Readiness state** (surfaces, capabilities, deployment targets,
  deviations) lives in `.cuelabs/project.yaml` — see
  [project-manifest.md](project-manifest.md).
- **Everything below** lives in the product's `docs/decisions.md`, under a
  `## Standard parameters` section, one row per parameter. `decisions.md` is
  already the product's ratification register, so a parameter changes the
  same way any other decision does.
- The standards repository never records a product's values. Examples in the
  references are illustrations, not assignments.

A parameter may be `n/a` when its surface is `absent` or `planned`; record it
when the surface becomes `active`.

## Parameters

| ID | Parameter | Allowed values / rule | Used by |
|----|-----------|-----------------------|---------|
| P-01 | Product slug (`<product>`) | Lowercase `[a-z0-9-]`, equal to the manifest `name`, the GitHub repo name, and the GitBook space | URLs, storage keys, image names, Discord channel |
| P-02 | Display name (`<Product>`) | Title-case brand name | Doc H1s, legal bar, metadata |
| P-03 | Marketing product slot | One short label naming the main audience or offering; must be a landing anchor, never an app route | Web marketing nav and footer |
| P-04 | Default theme | `light` or `dark` (what renders when the `<product>.theme` key is absent) | Web `ThemeProvider`, mobile theme, Figma default mode |
| P-05 | Playwright port (`PW_PORT` default) | 3100–3399, not used by any sibling product | Web e2e |
| P-06 | Settings IA | `tabs` (route-backed, default) or `hub` | Web and mobile settings |
| P-07 | Date idiom per surface class | `absolute`, `relative`, or `utc-absolute` for each surface class the product has | Web, mobile, `design.md` |
| P-08 | Command palette | `none`, or `⌘K/Ctrl+K` plus any extra aliases | Web a11y canon |
| P-09 | Data store | `postgres` or `firestore`, plus the product's `REDIS_DB` index | Backend, env, deploy |
| P-10 | Services and host ports | `api/common` 8080, `web` 3000, then each extra `api/<svc>` 8081+ in order added | Compose, Helm, `.env.example` |
| P-11 | Service transport | Per service pair: `http`, `grpc`, or `pubsub` (with the reason when not `http`) | Backend, delivery |
| P-12 | KYC tier contents | Tier-1 fields; tier-2 provider and trigger, or `n/a` | Profile, flows, `data-model.md` |
| P-13 | Destructive-confirm token | What the user types to arm account/data destruction (e.g. the org name) | Web and mobile danger ladder |
| P-14 | Discord channel | `#<product>-lab`; must exist on the CueLABS™ server before copy ships | Marketing copy |
| P-15 | Lint extensions | Each addition to the shared `eslint.config.mjs` base, with its reason, or `none` | Web tooling |
| P-16 | Mobile application ID | Reverse-DNS bundle/application id for the `prod` flavor (`dev` appends `.dev`) | Mobile flavors |

## Recording format

```markdown
## Standard parameters

| ID | Value | Notes |
|----|-------|-------|
| P-01 | acme | |
| P-04 | dark | |
| P-10 | api/common 8080 · web 3000 · api/ingest 8081 | |
```

Keep IDs stable. Adding a parameter is a standards change: add it here with a
new ID, and note it in the changelog so existing products can record their
value.
