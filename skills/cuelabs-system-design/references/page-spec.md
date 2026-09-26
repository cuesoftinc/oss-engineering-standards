# Design page spec

The page is generated from a JSON spec by `scripts/render_design.py`. The
script draws the SVG diagrams, builds every "Copy for Excalidraw" payload
from them, generates the "Copy as Mermaid" text from the same data, lays out
sequence diagrams, and checks the layout. `assets/example-spec.json` is a
complete, checker-clean example; start from it.

```bash
python3 <skill-dir>/scripts/render_design.py docs/system-design.json --check
python3 <skill-dir>/scripts/render_design.py docs/system-design.json --out docs/system-design.html
python3 <skill-dir>/scripts/render_design.py docs/system-design.json --out <tmp>/page.html --mode artifact
```

`standalone` (default) writes a full HTML document that opens in any
browser, with no network needed except the web fonts (the fallback fonts
work offline). `artifact` writes page content only, for hosts that wrap a
page in their own document skeleton.

## Contents

- Top level
- Sections
- Diagram sections
- Sequence sections
- Layout guidance
- The checker

## Top level

| Key | Meaning |
| --- | --- |
| `title` | A short name, e.g. "Acme System Design". No colon or dash explainer |
| `eyebrow` | Small line above the title, e.g. "Acme · system design v1" |
| `lead` | One or two sentences stating the design's thesis (HTML allowed: `code`, `strong`) |
| `status` | e.g. "Proposed v1 · awaiting ratification (S-1 to S-12)" |
| `theme` | Optional `{"light": {...}, "dark": {...}}` token overrides. Set `accent`, `accent-ink`, `accent-soft` from the product's design tokens when it has them |
| `sections` | Ordered list, below |
| `footer` | One line: what the page supersedes and what it keeps |

## Sections

Every section has `id` (unique, used for copy buttons), `type` and `title`,
and an optional `intro` paragraph.

| `type` | Extra keys | Renders |
| --- | --- | --- |
| `diagram` | `diagram`, `caption`, `legend` (bool) | A boxes-and-arrows SVG with Excalidraw and Mermaid copy buttons |
| `sequence` | `sequence`, `caption` | A sequence diagram laid out automatically |
| `table` | `columns`, `rows` | A table with an Excalidraw copy button. A cell is a string (HTML allowed) or `{"text" or "html", "class"}`; classes `kafka`, `http`, `store`, `sync`, `num` tint the cell |
| `rules` | `items: [{title, text}]` | A row of rule cards |
| `list` | `items: [{title, text}]` | A numbered list (open questions) |
| `text` | `html` | A paragraph |

Recommended order, matching the document: who it's for · the whole system
(with `legend: true`) · rules · what each service does · how the services
talk · what changes from the current design · two or three key flows ·
topics · decisions to ratify · still open.

Captions open with a bold one-line takeaway (`<strong>…</strong>`), then two
to four plain sentences.

## Diagram sections

```json
{"width": 1200, "height": 700, "aria": "One paragraph describing the diagram",
 "nodes": [{"id": "common", "kind": "service", "x": 240, "y": 250, "w": 260, "h": 74,
            "title": "api/common · Go", "lines": ["CRUD · auth", "outbox"]}],
 "edges": [{"from": "lb", "to": "common", "kind": "request", "label": "/api/v1/*",
            "points": [[370, 194], [370, 248]]}],
 "labels": [{"x": 378, "y": 224, "text": "/api/v1/* default", "kind": "muted"}]}
```

**Node kinds:** `client` (dashed: browsers, apps, providers, the load
balancer), `service` (Go or Node), `python`, `function`, `stock`, `store`,
`bus` (queue; its title sits inside, left-aligned), `person`, `chip` and
`chipbad` (small tags inside a larger node; use `"align": "top"` on the
parent so its title sits at the top), `group` (dashed outline around the
worker pools of one service; its `title` is drawn at `label_pos`, default
`bottom-right`), `labelbg` (a surface-coloured patch behind a label).
`font_size` shrinks a long title.

A box drawn fully inside another box (not a chip) makes the outer box a
**container**, for example "Apps" around the web and mobile boxes. Its title
is drawn small at its top-left, it becomes a Mermaid subgraph, and the boxes
inside it count as connected when the container is.

**Edge kinds:** `request`, `request-dashed`, `kafka`, `storage-write`,
`storage-read`, `cache`, `telemetry`, `sync`, `main`, `removed`, `lifeline`.
`arrow` is `end` (default), `start`, `both` or `none`. `cache` and
`telemetry` draw behind the nodes (so they pass under the queue bar); set
`layer` to override. `from`/`to` name nodes: they drive the Mermaid copy and
let the checker confirm the line starts and ends on those boxes. A branch
that merges into another line (several services feeding one telemetry line)
sets `"join": true`.

**Labels** are placed explicitly. `kind`: `muted`, `kafka`, `storage`,
`removed`, `sync`, `python`, `heading`, `title`, `sub`; `anchor`: `start`,
`middle`, `end`.

`mermaid` on a diagram overrides the generated Mermaid text.
`legend_labels` renames legend entries, e.g. `{"service": "Go (CRUD)"}`.

## Sequence sections

```json
{"aria": "…",
 "lanes": [{"id": "app", "title": "Mobile app", "sub": "user's phone", "kind": "client"}],
 "steps": [{"from": "app", "to": "c", "text": "POST /receipts", "kind": "request"},
           {"note": "checks consent · limits", "at": "c"},
           {"from": "c", "to": "app", "text": "201 + ticket", "kind": "reply"}],
 "footer": "One sentence on what happens next."}
```

Step kinds: `request`, `reply` (dashed), `kafka`, `storage-write`,
`storage-read`, `sync`, `removed`. A note sits to the right of its lane, or
to the left with `"side": "left"` (use it for the rightmost lane). Lanes are
spread evenly across `width` (default 1200) unless every lane has `x`.
Height follows the number of steps. `{"gap": 20}` adds space.

## Layout guidance

Diagrams read top to bottom. A proven grid for a whole-system diagram at
1200 wide:

| Row | y | Contents |
| --- | --- | --- |
| Clients | 30 | Browser, mobile app, providers that call us |
| Edge | 140 | web (left, 150 wide) and the load balancer (240 to 980) |
| Services | 250 | stores or providers at the left edge (x 20), `api/common` at x 240, gateways at x 560, object storage as a tall box at x 1000 |
| Queue | 390 | the bus from x 240 to 960, 46 tall |
| Processing | 500 | Python services or a pool group at x 240 and 560 |
| Support | 620 | cache, observability, AI provider |

Rules that keep diagrams readable:

- leave 50 to 60 px between rows for arrows and their labels;
- put a vertical arrow's label 6 to 8 px to the right of it (`start`
  anchor), or to the left with `end`;
- route shared lines (telemetry, cache) in the gaps between columns, behind
  the queue bar, and merge branches into one line;
- draw one service with several pools as a `group` around them;
- connect every box; a box with no line reads as not part of the system
  (set `"standalone": true` only for a deliberate legend-like box).

## The checker

`--check` reports, and `--strict` fails on:

- a node or label outside the canvas;
- a title or line wider than its box, or more rows than the box height fits;
- labels overlapping each other or a box;
- an edge whose ends don't touch the `from`/`to` boxes;
- a box with no line touching it;
- a diagram with no `from`/`to` edges (the Mermaid copy would be empty);
- a sequence message much wider than its arrow, or a note running off the
  canvas;
- a table row with the wrong number of cells;
- a diagram or sequence with no caption, or a title that reads like a caption.

Fix every warning before publishing. The checker estimates text width, so a
label it passes can still sit close to a line; look at the rendered page
once.
