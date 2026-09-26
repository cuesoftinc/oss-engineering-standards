# {{Product}} — Decisions

The ratification register for {{Product}}. Other docs defer to this file.

## Standard parameters

Values {{Product}} chooses where the CueLABS™ standard leaves a choice. The
IDs and allowed values are defined in `product-decisions.md` in the
`cuelabs-engineering-standards` skill. Leave a value as `—` until it is
decided; a parameter whose surface is `absent` or `planned` may read `n/a`.

| ID | Parameter | Value | Notes |
|----|-----------|-------|-------|
| P-01 | Product slug | {{product}} | Matches `name` in `.cuelabs/project.yaml` |
| P-02 | Display name | {{Product}} | |
| P-03 | Marketing product slot | — | |
| P-04 | Default theme | — | |
| P-05 | Playwright port | — | |
| P-06 | Settings IA | — | |
| P-07 | Date idiom per surface class | — | |
| P-08 | Command palette | — | |
| P-09 | Data store | — | |
| P-10 | Services and host ports | — | |
| P-11 | Service transport | — | |
| P-12 | KYC tier contents | — | |
| P-13 | Destructive-confirm token | — | |
| P-14 | Discord channel | — | Proposed: `#{{product}}-lab`; must exist before copy ships |
| P-15 | Lint extensions | — | |
| P-16 | Mobile application ID | — | |

## Decisions

Record each ratified decision below with a stable ID, the decision, and its
reason.
