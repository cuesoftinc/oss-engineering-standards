# CueLABS Shared Message Bus

Every CueLABS™ product that uses a queue shares **one Aiven Kafka service**,
the same way products share one Aiven Redis with `REDIS_DB` tenancy. This
page is the contract between those products. A product's
`docs/system-design.md` lists only its own events and points here for
topics, envelope, limits and operations.

Every product that uses Kafka is on the bus; there is no second Kafka
service to fall back to.

## The service's limits

Design every product to these, not to a larger cluster:

| Limit | Value | What it means for a design |
| --- | --- | --- |
| Topics | **5** for all products together | Products share topics ("lanes"); a product never creates its own |
| Partitions | 2 per topic | Ordering holds per key within a lane; throughput comes from small messages, not parallelism |
| Throughput | about 250 KiB/s in and out, for all products together | Messages carry pointers; bulk data (files, telemetry) never rides the bus |
| Retention | fixed by the service, up to 3 days; no compaction | No compacted config topics; never rely on the bus to keep anything longer than a day |
| Idle power-off | after 24 hours with no produce or consume, the service powers off, **drops all messages**, and stays off until powered on (minutes to hours) | The owner's store is the source of truth; stuck work is re-sent from it (see Operations) |
| Users and ACLs | a small number | One Kafka user per product, not per service |
| SLA | none | Uploads and other bus-dependent actions must fail cleanly while the bus is away |

## Lanes (topics)

| Topic | Direction | Carries |
| --- | --- | --- |
| `cuelabs.uploads` | a product's upload gateway → its control plane (`api/common`) | "a file is in `tmp/`" pointers |
| `cuelabs.requests` | a control plane → its processing services | work to do: extract, compute, segment, settle, alert… |
| `cuelabs.results` | processing services → their control plane | decisions and figures to store |
| *(reserved)* | — | two topics are held back; using one needs a decision in this file |

Create each with 2 partitions and the service's default retention. The
names never change per product: the **event type** says whose message it is.

## Message rules

1. **Envelope.** Every message is JSON:
   `{type, version, id, produced_at, data | data_ref}`. `type` is
   `<product>.<domain>.<event>` (for example `acme.import.ready`,
   `acme.capture.measured`). Each product validates its own events
   against JSON Schemas kept in its `api/common/contract/`.
2. **Read your product, skip the rest.** A consumer reads `type` first. An
   event from another product, or one of its own product's events that it
   doesn't handle, is committed and skipped silently: no schema validation,
   no error log. Only the events it handles are validated.
3. **Pointers, not data.** Every product can read every lane, so `data` may
   travel inline only when it holds identifiers, enums, counts and
   timestamps. Anything else (amounts, rows, names, file names, free text,
   measurements) goes by `data_ref`: the producer writes the JSON to its
   own product's storage prefix and sends the pointer. Storage IAM per
   product prefix is what keeps one product's data from another.
4. **Keys.** Use the entity id the order matters for (job, statement,
   session, org). Keys never contain personal data.
5. **No compacted topics.** Reference data and configuration a decision
   needs travel inside the request (by `data_ref` when large), or as a
   snapshot object in storage that the owner rewrites and a request names.
6. **Consumer groups** are `<product>-<service>[-<pool>]`, for example
   `acme-analytics-extract`. Each group keeps its own offsets, so one
   product's slow work never delays another's.
7. **Size.** Keep each message under 16 KB; pointers are small.

## What each product records

The bus has no registry here. Each product's own docs carry its part:

- `docs/system-design.md` §5.3 lists **only that product's events**, each
  with its lane, key, producer and consumers, and names this page as the
  source of lanes, envelope and limits.
- `docs/decisions.md` records "uses the shared bus", the product's Kafka
  user and consumer groups, and **which product is the keep-alive owner**
  (see Operations).
- A product joining the bus checks its expected message rate against the
  throughput limit, and moves bulk data off the bus before it joins.

Telemetry (spans, logs, metrics, product events, usage bytes) goes from the
ingest gateway to the OpenTelemetry Collector and on to its store directly,
never through the bus: its volume alone would exceed the service's
throughput.

## Scale to zero

Cloud Run services that consume run at **min 0 with CPU always allocated**.
Whoever publishes for a consumer that may be asleep wakes it with a
`GET /health` that carries no data (with a Cloud Run ID token when the target requires
authentication), debounced for about 10 seconds. Base URLs come from
`WAKE_<TARGET>_URL` settings; unset means "always running" (compose, Helm).
A product's scheduled sweep wakes its own services while its store shows
work in flight.

## Operations

- **Exactly one keep-alive owner.** One product's control-plane sweep
  sends a `<product>.system.heartbeat` on `cuelabs.requests` every 6 hours
  and, every few minutes, reads the service state from the Aiven API and
  powers it on when it is off (`AIVEN_API_TOKEN`, `AIVEN_PROJECT`,
  `AIVEN_KAFKA_SERVICE`, set only on that sweep). Every product's
  `docs/decisions.md` names the owner; no other product runs a heartbeat or
  a watchdog. If the owner leaves the bus, another product takes the role
  and every product's decision is updated.
- **Every product re-sends from its store.** Work still in progress after a
  few minutes is queued again, once, from the owner's database (the stored
  upload pointer and reference data), before it is failed. A power-off that
  dropped messages then costs a delay, not lost work.
- **Every product tolerates the bus being away.** Gateways answer 503 with
  a retry hint; control planes keep outbox rows until the bus accepts them.
- **Claim-check objects** live under `<product prefix>/compute/` and are
  deleted after a day (a sweep plus a bucket lifecycle rule).
- Connection settings are the fleet names: `KAFKA_BROKERS`,
  `KAFKA_USERNAME`, `KAFKA_PASSWORD`, `KAFKA_SSL_CA`, with SASL/SCRAM-SHA-256
  over TLS, using the product's own Kafka user.
