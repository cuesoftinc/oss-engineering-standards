# System design method

The rules and decision procedures behind a CueLABS system design. The
language-by-role pipeline rule itself is owned by
`$cuelabs-engineering-standards` (`repository-and-services.md`, "Multi-service
pipelines"); transports and serverless scope are owned by
`$cuelabs-delivery-standard` (`cloud-and-ci.md`). This file applies them to a
whole system and adds the patterns a design needs on top.

## Contents

- The rules
- Deciding the services
- Deciding how they communicate
- Deciding who owns the data
- Patterns
- Deployment
- Review checklist

## The rules

1. **Language by role.** Go (`api/common`) does CRUD only: it owns and
   persists data and never decides a value. Python does every decision:
   parsing, classification, scoring, ML/AI, money and tax arithmetic,
   anomaly detection, data-driven state machines. A Node gateway is thin:
   it validates and hands off. Serverless functions only for probe or
   health-check style endpoints.
2. **One owner per store.** Exactly one service reads and writes each
   database. Clients never read the database directly (no client-side
   database listeners); processing services never open the owner's store.
3. **Asynchronous by default.** Services hand work to each other through a
   durable queue. Every synchronous internal call is named, justified, and
   listed as a decision.
4. **Config flows outward, never by query.** The owner sends the
   configuration a decision needs inside the request, or rewrites a
   snapshot object in storage and announces the change with an event;
   consumers keep an in-memory copy and never query the owner. Don't depend
   on compacted topics: a shared or small queue service may not offer
   them.
5. **Users see progress, not a hanging request.** Every asynchronous step
   has a status row owned by the CRUD service that the client polls, with a
   push notification when the client may be in the background.
6. **The web mock is the contract.** When the web app has a mock API, the
   backend implements it; the design changes it only where the new shape
   forces a change, and lists those changes.
7. **Every service is observable.** OpenTelemetry from every service to the
   observability gateway; product events are counters only.

A "decision" is anything that computes or chooses a value. A lookup followed
by a write against data the owner already holds (create the row, flip a
status, expire a quote past its deadline) is CRUD, even when it runs on a
schedule.

## Deciding the services

Work through these in order. Name every service by function
(`api/<function>`), never by language.

| Question | If yes |
| --- | --- |
| Is there a user interface? | `web` (Next.js) and, when required, the mobile app |
| Is there any data to keep? | `api/common` (Go, CRUD owner). Always present for a backend |
| Do clients send files or large payloads, or does a third party push high-volume data (telemetry, events)? | A **gateway** (Node): one per ingress shape, stateless |
| Does anything compute or choose a value? | A **processing service** (Python) |
| Are reads expensive or analytical, on a separate store (columnar, search)? | A **read service** (Go, read-only), so a heavy query can't starve CRUD |
| Is there stateless work that must run from several regions or scale to zero between rare calls (probes)? | **Serverless functions**, and only for that |
| Does an existing component already do the job (collector, database-native queue ingestion)? | Use the **stock component**; write no custom loader |

### How many processing services

Start from one. Split into a second service only when at least one of these
is true, and say which one in the design:

- **Urgency differs.** One path pages a human or blocks a user (an outage
  alert, a payment confirmation), and another is background (ML insights,
  narratives).
- **Resources differ sharply.** One path needs GPU or multi-GiB inference,
  the other is light arithmetic.
- **Failure domains must be isolated.** Money movement must not share a
  process with experimental ML.
- **Credentials differ.** One path holds a payment or provider secret the
  other must never see.

When the paths differ only in speed or volume, but share vocabulary, schemas,
team and release cadence, keep **one service and run it as several worker
pools** from the same image (an environment variable selects the pool). Draw
it as one service with the pools inside it. Record the split-or-pool choice
as a decision; it is often the user's to make.

### Ports

`api/common` 8080, then each service in the order it was added. A renamed
service keeps its port.

## Deciding how they communicate

| Traffic | Transport |
| --- | --- |
| Browser or app to backend | HTTPS/JSON on one API host, routed by path at a load balancer. The browser runs the app and calls the API directly (CORS allowlist); the web server only serves the app and server-renders public pages |
| Sign-in | The client signs in with the identity provider's SDK and sends its ID token; services verify tokens locally with the provider's public keys |
| File upload | Create-then-upload with an **upload ticket** (Patterns) |
| Service to service | The queue (Kafka by default). No gRPC between services. The one exception is a data-free wake-up call that starts a consumer scaled to zero (Deployment) |
| A call that needs its answer inline and targets a stateless callee (a probe), or a read against the read service | Synchronous HTTPS with the platform's service identity; list it as a decision |
| Third party calls us (webhooks) | Through the load balancer to the owner of the affected data: verify the signature, store the raw event, publish it; a processing service interprets it |
| We call a third party to fetch data | From the service holding the credential, usually the CRUD owner (fetch and relay); decisions about the fetched data still go through processing |
| We call a third party because of a decision (payout, refund, notification) | From the processing service that made the decision, idempotent by a stable key |
| Telemetry | OTLP directly from every service to the observability gateway |

A diagram must show these directions truthfully: inbound webhooks enter
through the load balancer; outbound provider calls leave directly.

## Deciding who owns the data

- The CRUD service owns every relational store and its schema (migrations
  live with it).
- A gateway owns nothing: no database, no cache state that other requests
  depend on. Limits and quotas are enforced by the owner before a ticket is
  issued.
- A processing service owns nothing. It receives reference data inside the
  message (scoped to what the decision needs, e.g. fingerprints for the
  relevant date window only), or by pointer when large. Its only state is
  in-memory and rebuildable from the next request or a config snapshot.
- Object storage is split by prefix: `tmp/` for bytes awaiting a decision
  (short lifetime), durable prefixes for confirmed media and artifacts.
- The cache holds rate limits and quotas; it is never a source of truth.
  Losing it must be survivable.
- Tenancy is enforced twice: in the owner's authorization layer and with
  row-level security.

## Patterns

**Upload tickets.** The client first calls the owner with a small JSON
request (declared type and size, idempotency key). The owner checks
everything it alone can see (consent, ownership, role, account state, rate
limits, byte quota), creates the record in `awaiting_upload`, and returns a
short-lived (about 5 minutes), single-use ticket signed with an asymmetric
key. The client sends the bytes with the ticket to the gateway, which
verifies the signature with the public key, checks the file against the
ticket's limits, strips sensitive metadata (EXIF/GPS), writes to `tmp/`, and
publishes a pointer. Nothing is stored before authorization; the gateway
never holds a key that can mint tickets. Tickets also scope retakes (one pose,
one page) and replace a shared session secret.

**Claim-check.** Bytes live in object storage; messages carry pointers.
Any payload that could exceed a few hundred KB goes by pointer. When the
queue is shared with other products, every payload that holds more than
identifiers, enums, counts and timestamps goes by pointer, so storage
permissions, not topic permissions, keep each product's data private.

**Raw-data lifetime.** Delete temporary bytes as soon as the decision is
recorded (by the owner), sweep leftovers on a short schedule, and keep a
bucket lifecycle rule as the last backstop. State the lifetime in the
privacy disclosure.

**Outbox.** A write and its outbox row commit in one transaction; a
publisher sends rows to the queue and stamps them. Use it for every message
the owner produces.

**Versioned results.** When processing computes figures from the owner's
data (tax, ratios, validations), the owner bumps a data version on every
relevant change and requests a recompute; results carry the version they
used and are stored only if it is still current. A user action that depends
on a computed check (confirm) reads the stored, current result synchronously
instead of computing inline.

**Raw provider events.** Store every inbound webhook before acting on it,
unique by the provider's event id.

**Event naming.** Every message's type is `<product>.<domain>.<event>`,
JSON validated against JSON Schemas kept with the owner
(`api/common/contract/`). A product with its own queue service may give
each event its own topic. On a **shared** queue service, products share a
few topics ("lanes", by direction) and consumers read the type first,
skipping other products' events and events they don't handle without
validating or logging them. Follow the organization's messaging profile
for lane names and limits when it has one (for CueLABS™:
`cuelabs-delivery-standard/references/shared-messaging.md`). Retention
follows sensitivity and the service's limits; design so that nothing
depends on the queue keeping a message for more than a day.

**Re-send from the owner.** The owner stores what each in-flight request
was built from (the upload pointer, the reference data inputs). A sweep
queues a request again, once, when its result is overdue, before it fails
the item. A lost message then costs a delay, not lost work.

## Deployment

- Queue consumers never scale to zero by themselves: a message does not
  wake a scaled-to-zero instance. Run them as worker pools; or at a minimum
  of one instance with instance-based billing (CPU always allocated); or at
  zero with **wake-ups**: CPU always allocated while an instance is up, and
  whatever publishes for a consumer sends it a data-free request
  (`GET /health`) afterwards so the platform starts an instance, with the
  owner's sweep re-waking services while its store shows work in flight.
  Say what the choice costs against any free-tier goal.
- Request-driven services with no consumer may scale to zero.
- Scheduled lookup-then-write work runs as scheduled jobs from the owner's
  image; scheduled decisions run from the processing image.
- Every managed dependency needs a single-container self-host equivalent.

## Review checklist

Before publishing, confirm:

- every box on every diagram is connected to something;
- one service with several pools is drawn as one service;
- every line style and box style used appears in the legend;
- inbound and outbound third-party traffic are drawn in their real direction;
- no service other than the owner touches a store;
- every synchronous internal call is listed as a decision;
- every behaviour change to an existing contract is listed (the doc map and
  the mock changes);
- every product decision the design reverses is flagged for sign-off.
