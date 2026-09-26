---
name: cuelabs-system-design
description: Design or redesign a product's backend system the CueLABS way and publish it as a document plus an interactive diagram page. Use when asked for a system design, architecture, service breakdown, or architecture diagram from a PRD, an existing repository, or a plain description; to decide how many services a product needs, which language each uses, how they communicate (HTTP, Kafka, webhooks, uploads), and who owns each data store; or to update an existing system design. Produces docs/system-design.md and a self-contained HTML page with Excalidraw and Mermaid copy buttons, publishable as an artifact where the client supports it.
---

# CueLABS System Design

Turn a product's requirements into a system design that follows the CueLABS
language-by-role rule, then publish it twice: as a document in the
repository, and as a diagram page people can open in any browser or copy
into Excalidraw.

## Read the relevant references

- Read [references/method.md](references/method.md) before deciding
  anything. It holds the rules, how to choose the services, how they
  communicate, who owns the data, the reusable patterns (upload tickets,
  claim-check, outbox, versioned results), and the review checklist.
- Read [references/document-template.md](references/document-template.md)
  when writing `docs/system-design.md`.
- Read [references/page-spec.md](references/page-spec.md) when writing the
  page spec, and start from
  [assets/example-spec.json](assets/example-spec.json).
- The pipeline rule itself is owned by `$cuelabs-engineering-standards`
  (`repository-and-services.md`); transports, serverless scope and fleet
  environment names are owned by `$cuelabs-delivery-standard`
  (`cloud-and-ci.md`). Consult them when installed; do not restate them.

## Inputs

Accept any of these, alone or together:

- **Product documents**: a PRD, decisions register, architecture, data
  model, flow docs, deployment docs, API docs, a web mock API.
- **A repository**: read the documents first, then the code only to confirm
  what exists. If the user says to ignore the code, design from the
  documents alone.
- **A description**: a few paragraphs about the product.

When the input is thin, ask at most three questions that change the design
(who uses it, what data is sensitive, what third parties it touches, what is
urgent). Otherwise proceed and record assumptions as open questions.

## Workflow

1. **Gather.** Read everything relevant. List the product's users, core
   flows, data (with sensitivity), third parties, money movement, privacy
   promises, and every existing ratified decision. Existing product decisions
   stay unless the design must reverse one; a reversal is flagged for
   sign-off, never silent.
2. **Audit.** Compare the current design (documents, draft diagrams, code
   when in scope) against the rules in `method.md`. Write findings with
   evidence and consequence. For a description-only input, write the
   starting facts and assumptions instead.
3. **Drivers.** Name the five to nine properties this product must have and
   the mechanism that delivers each.
4. **Services.** Apply "Deciding the services" in `method.md`. Decide the
   number of processing services with the split criteria; when the choice
   is close, present it to the user with a recommendation before writing
   the rest. Present the transport choice the same way when it is open
   (for example Kafka versus a managed pub/sub with push delivery).
5. **Communication and data.** Apply the communication table and the data
   ownership rules. Add the patterns the flows need: upload tickets for any
   client upload, claim-check for bytes, outbox for everything the owner
   publishes, versioned results for anything computed from the owner's
   data, raw storage for inbound webhooks.
6. **Flows.** Pick two to four flows that exercise the design end to end and
   write them as sequences, including authorization, polling, failures and
   deletion.
7. **Remaining sections.** API surface and contract changes, security,
   reliability (SLOs, failure modes, who watches it), deployment (worker
   pools for consumers), repository layout, doc map, decisions to ratify
   (`S-1…`), migration phases, open questions.
8. **Write the document** to `docs/system-design.md` (or the path the user
   names) following `document-template.md`. Do not commit unless asked.
9. **Write the page spec** to `docs/system-design.json` next to it. Include
   at least: the whole system (with legend), rules, services table,
   communication table, what changes from the current design (when there is
   one), the key flows as sequences, topics, decisions, open questions.
10. **Check and render.**

    ```bash
    python3 <skill-dir>/scripts/render_design.py docs/system-design.json --check --strict
    python3 <skill-dir>/scripts/render_design.py docs/system-design.json --out docs/system-design.html
    ```

    Fix every warning. If the environment can screenshot a page (a headless
    browser), look at the rendered page once and fix what it shows.
11. **Publish.**
    - Always leave `docs/system-design.html`: a self-contained page anyone
      can open in a browser, with working copy buttons.
    - If the client can publish HTML pages (for example an artifacts or
      pages tool), render with `--mode artifact` to a temporary path and
      publish that file; give the user the link. When updating a design
      published earlier, publish to the same page so its link keeps working.
    - Tell the user who can see a published page if the tool reports it.
12. **Iterate.** When the user questions or changes something, update the
    document and the spec together, re-run the checker, re-render, and
    republish to the same page. Keep service names, topics and decision IDs
    identical across both.

## Guardrails

- Never give a gateway or a processing service its own connection to the
  owner's database, even when a request asks for it; explain the rule and
  list the request as an open question for sign-off.
- Never let bytes reach storage before the owner has authorized the upload.
- Never leave a box unconnected on a diagram, or draw one service with
  several worker pools as two services.
- Never draw an inbound provider call as skipping the load balancer, or an
  outbound call as passing through it.
- Never invent a product value the inputs do not support; list it as an
  open question.
- Never reverse a ratified product decision without flagging it for sign-off.
- Never name another product in a design unless it is a real dependency of
  this one (for example the shared observability gateway).
- Keep secrets out of specs, pages and documents; name environment variables
  only.

## Result format

Report, in this order:

1. the service lineup with one line each on why it exists;
2. the choices you made that the user may want to revisit (split versus
   pools, transport), with your recommendation;
3. decisions that need a stakeholder's sign-off;
4. the paths written (`docs/system-design.md`, `.json`, `.html`) and the
   published link if any;
5. checker result and whether the page was visually checked.
