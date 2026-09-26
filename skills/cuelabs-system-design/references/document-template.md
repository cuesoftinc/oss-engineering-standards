# System design document template

Write the design to `docs/system-design.md` in the product repository unless
the user names another path. Use these sections in this order; omit a section
only when it genuinely does not apply, and say so in one line.

## Header

A blockquote stating: status (`[Proposed] v1 — draft for ratification`),
which existing docs and sections it replaces once ratified, that it keeps
every product decision and behavioural contract (name the exceptions), and
where the new decisions are listed (`§13 as S-1…S-n`). Then the language rule
in four bullets (see `method.md`) and one line on naming and transport.

## 1. Why redesign — audit of the current design

State what was audited (documents, a repository, or a description). Then a
findings table:

| # | Finding | Evidence | Consequence |
| --- | --- | --- | --- |
| F1 | One-sentence problem in bold | The doc section, file, or quote | What goes wrong because of it |

Close with one paragraph: "What is solid and carries forward". For a
description-only input with nothing to audit, title the section "Starting
point" and list the facts and assumptions instead.

## 2. Design drivers

| # | Driver | Design response |
| --- | --- | --- |
| D1 | The property the product must have | The concrete mechanism that delivers it |

Five to nine drivers. Tie each to the product (its sensitive data, its
urgency, its money, its privacy promises), not to generic virtues.

## 3. Architecture overview

One Mermaid flowchart of the whole system, consistent with the page's
overview diagram.

## 4. Services

A table: Unit · Lang · Role · Responsibility · Owns · Port. Then
**Retired:** (what disappears) and **Why these boundaries:** (one bullet per
non-obvious boundary, including any split-or-pool choice).

## 5. Data architecture

- 5.1 Stores and ownership: Store · Holds · Written by · Read by · Source of
  truth?
- 5.2 The owner's schema additions this design needs, as a table with a
  "Why" column.
- 5.3 Queue topics: Topic · Key · Retention · Producer → consumers.

## 6. Key flows

Two to four Mermaid sequence diagrams for the flows that exercise the design
(an upload, a money or compute path, a sync or webhook path), each followed
by bullets for the rules the diagram can't show (authorization, timeouts,
retakes, deletion). Then config propagation and a scheduled-jobs table.

## 7. API surface

Hosts and routing, protocol stance, and "the web mock is the contract" with
the exact list of contract changes.

## 8. Security and tenancy

A table: Concern · Control. Cover user auth, authorization, tenancy, machine
identity (queue ACLs, storage IAM per prefix), provider credentials,
privacy, secrets, abuse.

## 9. Reliability, failure modes, and capacity

SLOs, a failure-mode table (Failure · What happens), who watches the system,
and a capacity sketch with real units.

## 10. Deployment topology

Cloud units with their runtime kind and scaling, self-host equivalents, and
environment variable names (new and retired).

## 11. Repository layout

A tree of the target layout.

## 12. Doc map — keep, change, retire

Doc · Fate, for every existing document the design touches.

## 13. Decisions to ratify

| ID | Decision | Supersedes | Recommendation |
| --- | --- | --- | --- |
| S-1 | Units: … | What it replaces | ⭐ ratify, or what needs sign-off |

Mark every reversal of an existing product decision as needing explicit
sign-off. Close with what to update on ratification.

## 14. Migration plan

Phases with Delivers · Exit criteria · Maps to (the product's roadmap). State
whether any data migration is needed.

## 15. Open questions

Numbered, each a question the user or a stakeholder must answer, with the
options and a recommendation where there is one.

## Writing rules

- Evidence over assertion: every finding cites where it came from.
- Name things by what they do; keep paragraphs short; prefer tables.
- Never invent a product value (a slug, a port already taken, a provider)
  the inputs don't support; list it as an open question instead.
- Keep the document and the page consistent: same service names, topics,
  decision IDs and numbers.
