<div align="center">

# Tessel

**A multi-tenant telemetry backend for agricultural edge sensors.**

Devices on unreliable rural networks push batched soil readings. Tessel stores each reading exactly once, keeps every organization's data isolated, raises alerts, and notifies other systems through signed webhooks.

[![CI](https://github.com/sdukea/tessel/actions/workflows/ci.yml/badge.svg)](https://github.com/sdukea/tessel/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white)

[Architecture](#architecture) · [Core flows](#core-flows) · [Data model](#data-model) · [API](#api-overview) · [Quickstart](#quickstart) · [Design decisions](#design-decisions)

</div>

> [!NOTE]
> Tessel is under active development. Sections marked **🚧 pending** describe planned work, and performance figures are filled in from real load tests as each milestone ships. See the [roadmap](#roadmap).

---

## Table of contents

- [Why Tessel](#why-tessel)
- [Guarantees](#guarantees)
- [Architecture](#architecture)
- [Core flows](#core-flows)
- [Data model](#data-model)
- [API overview](#api-overview)
- [Security model](#security-model)
- [Capacity and performance](#capacity-and-performance)
- [Tech stack](#tech-stack)
- [Quickstart](#quickstart)
- [Configuration](#configuration)
- [Testing](#testing)
- [Observability](#observability)
- [Project structure](#project-structure)
- [Design decisions](#design-decisions)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Contributing](#contributing)

---

## Why Tessel

Farm sensors live at the edge of the network. A soil probe in a field might sit on a weak 2G link that drops responses mid-request, so the device retries and the server sees the same batch twice. A worker can crash between saving an alert and sending it, and the alert is lost. One organization's agronomist must never see another organization's fields.

None of these problems is solved by CRUD alone. Tessel is designed around the failures it prevents, and every feature can be traced back to one:

| Failure | What goes wrong without it | How Tessel handles it |
|---|---|---|
| Lost responses on rural networks | Retries insert duplicate readings | `Idempotency-Key` per batch, enforced by a Postgres unique constraint |
| Crash between "save alert" and "send alert" | Alerts vanish silently | **Transactional outbox**: the alert and its event commit together |
| Two workers grabbing the same job | Double delivery or lost work | `FOR UPDATE SKIP LOCKED` claims with leases |
| A forgotten `WHERE org_id = …` | Cross-tenant data leak | Tenant-scoped repositories that cannot run a query without an org filter |
| Slow or failing weather API | Requests pile up and the API stalls | Timeouts, jittered retries, a Redis cache and a circuit breaker |
| A stolen device | Indefinite unauthorized writes | Hashed, revocable API keys with two-key rotation |
| A runaway device | One tenant degrades the platform | Per-device and per-org rate limits in Redis |
| Spoofed or replayed webhooks | Integrators act on forged events | HMAC signatures per [Standard Webhooks](https://www.standardwebhooks.com/) with timestamps |
| Webhook URL pointing at internal hosts | Server-side request forgery (SSRF) | DNS resolution and private-range rejection at registration and send time |

### Who uses it

| Actor | Authenticates with | Does |
|---|---|---|
| **Edge devices** | API key (`X-Device-Key`) | Push batched readings |
| **People** (owner, admin, member, viewer) | Password → JWT + rotating refresh token | Manage farms and devices, view data and advice |
| **Integrators** (e.g. irrigation controllers) | Webhook signing secret | Receive signed `alert.created` events |
| **Weather provider** ([Open-Meteo](https://open-meteo.com/)) | None | Supplies forecasts for irrigation advice |

---

## Guarantees

| Property | Guarantee | Mechanism |
|---|---|---|
| Ingestion | **Effectively exactly-once** storage of readings under client retries | Idempotency keys + `UNIQUE (device_id, metric, recorded_at)` as a second safety net |
| Alert delivery | **At-least-once**, with receiver-side deduplication via `webhook-id` | Transactional outbox + leased deliveries + exponential backoff |
| Tenant isolation | No query can cross an org boundary | Org in the URL, membership check per request, tenant-scoped repositories |
| Graceful shutdown | No in-flight work is lost on deploy | `SIGTERM` handling: finish the batch, commit, exit |
| Error contract | Every error has one machine-readable shape | [RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) `application/problem+json` |

---

## Architecture

Two processes built from one image, two data stores, and one outside dependency.

```mermaid
flowchart LR
    subgraph Clients
        D["Edge devices"]
        U["People<br/>(dashboard / CLI)"]
    end

    subgraph Tessel
        API["API service<br/>FastAPI, async"]
        W["Worker process<br/>outbox + delivery loop"]
    end

    PG[("PostgreSQL 17<br/>data · outbox · deliveries")]
    R[("Redis 7<br/>rate limits · cache")]
    OM["Open-Meteo<br/>weather API"]
    S["Subscriber endpoints<br/>(integrators)"]

    D -- "X-Device-Key + Idempotency-Key<br/>batched readings" --> API
    U -- "Bearer JWT" --> API
    API -- "SQL, one transaction per batch" --> PG
    API -- "INCR / EXPIRE, cache" --> R
    API -- "forecasts, behind breaker" --> OM
    W -- "FOR UPDATE SKIP LOCKED" --> PG
    W -- "HMAC-signed POST + retries" --> S
```

### Layering

The domain is plain Python with no I/O. It defines **ports** (Protocols) that infrastructure **adapters** implement, so business rules test in milliseconds and survive framework or database changes. Dependencies point inward only.

```mermaid
flowchart TB
    subgraph Edge["api/ — HTTP edge"]
        R1["Routers · Pydantic schemas<br/>auth & permission dependencies"]
    end
    subgraph Domain["domain/ — pure Python"]
        M["Models: Reading, Alert, Metric"]
        RU["Rules: ThresholdRule,<br/>RateOfChangeRule"]
        P["Ports: ReadingRepository,<br/>WeatherProvider"]
    end
    subgraph Infra["infra/ — adapters"]
        DB["Postgres repositories<br/>(tenant-scoped)"]
        WX["OpenMeteoClient<br/>retries · cache · breaker"]
        WH["Webhook sender<br/>signing · SSRF guard"]
    end

    R1 --> M
    R1 --> RU
    R1 --> P
    DB -. implements .-> P
    WX -. implements .-> P
    R1 --> DB
    R1 --> WX
```

---

## Core flows

### 1. Idempotent batch ingestion

A device generates a UUID per batch and sends it as `Idempotency-Key`. Everything below happens in **one database transaction**, so a retry either replays the stored response or does the work for the first time. It never does it twice.

```mermaid
sequenceDiagram
    autonumber
    participant Dev as Device
    participant API as API service
    participant RL as Redis
    participant DB as PostgreSQL

    Dev->>API: POST /v1/ingest/readings<br/>X-Device-Key, Idempotency-Key, batch (≤500)
    API->>API: Verify key (prefix lookup + constant-time hash compare)
    API->>RL: INCR device and org counters (pipeline)
    alt over limit
        API-->>Dev: 429 Too Many Requests + Retry-After
    end
    API->>DB: BEGIN
    API->>DB: INSERT idempotency_keys ... ON CONFLICT DO NOTHING RETURNING
    alt key already exists
        API->>DB: SELECT stored response
        alt same request hash
            API-->>Dev: Replay original status + body
        else different body, same key
            API-->>Dev: 422 key reused with different payload
        end
    else new key
        API->>DB: INSERT readings (single statement, ON CONFLICT DO NOTHING)
        API->>API: Evaluate alert rules (domain layer)
        API->>DB: INSERT alerts + outbox_events (alert.created)
        API->>DB: UPDATE idempotency_keys SET response
        API->>DB: COMMIT
        API-->>Dev: 201 Created
    end
```

### 2. Transactional outbox → webhook delivery

The API never calls a subscriber directly. The alert and its `outbox_events` row commit atomically, and a separate worker fans events out to webhook deliveries. Network calls happen **outside** any open transaction, guarded by a lease.

```mermaid
sequenceDiagram
    autonumber
    participant DB as PostgreSQL
    participant W as Worker
    participant S as Subscriber

    loop poll
        W->>DB: BEGIN, then SELECT ≤50 due outbox_events<br/>FOR UPDATE SKIP LOCKED
        W->>DB: INSERT webhook_deliveries (one per matching endpoint)
        W->>DB: UPDATE outbox_events SET status='done', then COMMIT
    end
    loop deliver
        W->>DB: Claim due deliveries<br/>status='in_flight', locked_until = now()+lease, then COMMIT
        W->>W: Re-check URL resolves to a public IP
        W->>S: POST (10 s timeout, no redirects)<br/>webhook-id, webhook-timestamp, webhook-signature
        alt 2xx
            W->>DB: status='delivered'
        else error / timeout
            W->>DB: attempts += 1, next_attempt_at = backoff(attempts)
        end
    end
```

### 3. Webhook delivery lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending: created from outbox event
    pending --> in_flight: worker claims (lease)
    in_flight --> delivered: 2xx response
    in_flight --> pending: failure, retry at 1m · 5m · 30m · 2h · 6h
    in_flight --> pending: lease expires (worker crashed)
    in_flight --> failed: retries exhausted
    failed --> pending: manual redeliver
    delivered --> [*]
    failed --> [*]
```

Endpoints that fail persistently are auto-disabled. Delivery history is exposed through a delivery log endpoint, and any delivery can be replayed with `redeliver`.

### 4. Session auth with refresh-token rotation

Access tokens are short-lived JWTs verified without a database lookup. Refresh tokens are random, stored only as hashes, and rotated on every use. Presenting an already-used token signals theft and **revokes the whole token family**.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant API as API service
    participant DB as PostgreSQL

    C->>API: POST /v1/auth/login (email, password)
    API->>DB: Load user (or verify a dummy hash to equalize timing)
    API->>API: Argon2id verify
    API->>DB: Store hash(refresh₁), family F
    API-->>C: access JWT (15 min) + refresh₁

    C->>API: POST /v1/auth/refresh (refresh₁)
    API->>DB: Mark refresh₁ used, store hash(refresh₂) in F
    API-->>C: new access JWT + refresh₂

    Note over C,API: An attacker replays the stolen refresh₁
    C->>API: POST /v1/auth/refresh (refresh₁)
    API->>DB: refresh₁ already used → revoke all tokens in F
    API-->>C: 401 Unauthorized
```

### 5. Irrigation advice that survives a failing dependency

Advice combines the latest soil moisture with the next 24 hours of forecast rain and returns `irrigate`, `hold` or `insufficient_data` with a reason. The weather adapter is wrapped in a circuit breaker so a slow upstream never stalls the API.

```mermaid
stateDiagram-v2
    [*] --> Closed
    Closed --> Closed: success (reset failure count)
    Closed --> Open: 5 consecutive failures
    Open --> HalfOpen: after 60 s
    HalfOpen --> Closed: trial call succeeds
    HalfOpen --> Open: trial call fails
    note right of Open
        Skip upstream calls.
        Serve cached forecast
        with stale: true
    end note
```

| Layer | Policy |
|---|---|
| Timeouts | Connect 2 s, read 5 s |
| Retries | Up to 3, on timeouts, `429`, `502`, `503`, `504`; exponential backoff with full jitter; honours `Retry-After` |
| Cache | Redis, 30 min TTL, keyed by lat/lon rounded to 2 decimals (~1 km) |
| Validation | Upstream responses parsed through a Pydantic model before use |

---

## Data model

Every tenant-owned table carries `org_id`, including `devices` and `readings`, so tenant filters never need a join.

```mermaid
erDiagram
    ORGANIZATIONS ||--o{ MEMBERSHIPS : has
    USERS ||--o{ MEMBERSHIPS : has
    USERS ||--o{ REFRESH_TOKENS : holds
    ORGANIZATIONS ||--o{ FARMS : owns
    FARMS ||--o{ DEVICES : contains
    DEVICES ||--o{ DEVICE_KEYS : "authenticates with"
    DEVICES ||--o{ READINGS : records
    DEVICES ||--o{ IDEMPOTENCY_KEYS : sends
    ORGANIZATIONS ||--o{ ALERT_RULES : defines
    ALERT_RULES ||--o{ ALERTS : triggers
    ORGANIZATIONS ||--o{ OUTBOX_EVENTS : emits
    ORGANIZATIONS ||--o{ WEBHOOK_ENDPOINTS : registers
    WEBHOOK_ENDPOINTS ||--o{ WEBHOOK_DELIVERIES : receives
    OUTBOX_EVENTS ||--o{ WEBHOOK_DELIVERIES : "fans out to"

    MEMBERSHIPS {
        uuid user_id FK
        uuid org_id FK
        text role "owner | admin | member | viewer"
    }
    DEVICES {
        uuid id PK
        uuid org_id FK
        uuid farm_id FK
        text serial_number "UNIQUE (org_id, serial_number)"
    }
    READINGS {
        bigint id PK "identity"
        uuid org_id FK
        uuid device_id FK
        text metric
        float value "CHECK per-metric range"
        timestamptz recorded_at "UNIQUE (device_id, metric, recorded_at)"
    }
    IDEMPOTENCY_KEYS {
        uuid device_id FK
        uuid key "UNIQUE (device_id, key)"
        text request_hash
        int response_status
        jsonb response_body
        timestamptz created_at
    }
    OUTBOX_EVENTS {
        uuid id PK
        uuid org_id FK
        text type "alert.created"
        jsonb payload
        text status
        int attempts
        timestamptz next_attempt_at
    }
    WEBHOOK_DELIVERIES {
        uuid id PK
        uuid endpoint_id FK
        uuid event_id FK
        text status "pending | in_flight | delivered | failed"
        int attempts
        timestamptz locked_until
        timestamptz next_attempt_at
    }
```

**Indexing.** The hot read path, "latest N readings for a device", is served by `(device_id, recorded_at DESC, id DESC)`. That index also backs **keyset pagination**: cursors encode `(recorded_at, id)` of the last row, so page 1,000 costs the same as page 1, and results stay stable while new readings arrive.

---

## API overview

All routes are versioned under `/v1`. Tenant resources are nested under `/v1/orgs/{org_id}`, and a caller who is not a member of that org receives `404`, not `403`, so the existence of other tenants is never revealed. Public IDs are UUIDs to prevent enumeration. The full contract is served as OpenAPI at `/docs` and `/openapi.json`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| `POST` | `/v1/auth/register` | – | Create a user |
| `POST` | `/v1/auth/login` | – | Issue access + refresh tokens |
| `POST` | `/v1/auth/refresh` | Refresh token | Rotate the token pair |
| `POST` | `/v1/auth/logout` | Refresh token | Revoke the refresh token |
| `GET` `POST` | `/v1/orgs/{org_id}/farms` | JWT | List / create farms |
| `GET` `POST` | `/v1/orgs/{org_id}/farms/{farm_id}/devices` | JWT | List / register devices |
| `GET` `PATCH` `DELETE` | `/v1/orgs/{org_id}/devices/{device_id}` | JWT | Manage a device |
| `POST` | `/v1/orgs/{org_id}/devices/{device_id}/keys` | JWT `devices:write` | Issue or rotate a device key (shown once) |
| `DELETE` | `/v1/orgs/{org_id}/devices/{device_id}/keys/{key_id}` | JWT `devices:write` | Revoke a device key |
| `GET` | `/v1/orgs/{org_id}/devices/{device_id}/readings` | JWT | Keyset-paginated readings |
| `POST` | `/v1/ingest/readings` | Device key + `Idempotency-Key` | Ingest a batch of up to 500 readings |
| `GET` | `/v1/orgs/{org_id}/farms/{farm_id}/irrigation-advice` | JWT | Soil + forecast → advice |
| `GET` `POST` `DELETE` | `/v1/orgs/{org_id}/webhooks` | JWT `webhooks:write` | Manage webhook endpoints |
| `GET` | `/v1/orgs/{org_id}/webhooks/{id}/deliveries` | JWT | Delivery log |
| `POST` | `/v1/orgs/{org_id}/webhooks/{id}/deliveries/{delivery_id}/redeliver` | JWT `webhooks:write` | Replay a delivery |
| `GET` | `/health` · `/ready` · `/metrics` | – | Liveness, readiness, Prometheus |

<details>
<summary><b>Example: ingest a batch</b></summary>

```bash
curl -X POST http://localhost:8000/v1/ingest/readings \
  -H "X-Device-Key: tsl_live_ab12cd34.<secret>" \
  -H "Idempotency-Key: 6f1c2a9e-3d4b-4e8a-9f71-1c2b3d4e5f60" \
  -H "Content-Type: application/json" \
  -d '{
    "readings": [
      {"metric": "soil_moisture", "value": 23.4, "recorded_at": "2026-10-25T06:00:00Z"},
      {"metric": "air_temp",      "value": 14.1, "recorded_at": "2026-10-25T06:00:00Z"},
      {"metric": "battery",       "value": 87,   "recorded_at": "2026-10-25T06:00:00Z"}
    ]
  }'
```

Sending the same request again with the same `Idempotency-Key` returns the identical response and stores nothing new.

</details>

<details>
<summary><b>Example: error response (RFC 9457)</b></summary>

```json
{
  "type": "/problems/validation-error",
  "title": "Request validation failed",
  "status": 422,
  "detail": "readings[2].value: soil_moisture must be between 0 and 100",
  "instance": "/v1/ingest/readings"
}
```

</details>

<details>
<summary><b>Example: verifying a webhook (receiver side)</b></summary>

```python
import base64, hashlib, hmac, time

def verify(secret: str, headers: dict, body: bytes, tolerance_s: int = 300) -> bool:
    msg_id = headers["webhook-id"]
    ts = int(headers["webhook-timestamp"])
    if abs(time.time() - ts) > tolerance_s:          # reject replays
        return False
    key = base64.b64decode(secret.removeprefix("whsec_"))
    signed = f"{msg_id}.{ts}.".encode() + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    return any(
        hmac.compare_digest(expected, sig.split(",", 1)[1])
        for sig in headers["webhook-signature"].split()
        if sig.startswith("v1,")
    )
```

</details>

---

## Security model

```mermaid
flowchart LR
    REQ["Incoming request"] --> AUTHN{"Authenticate"}
    AUTHN -- "Bearer JWT" --> USER["get_current_user<br/>verify signature + exp"]
    AUTHN -- "X-Device-Key" --> DEV["get_current_device<br/>prefix lookup + compare_digest"]
    AUTHN -- "neither / invalid" --> R401["401"]
    USER --> MEM{"Member of org_id?"}
    MEM -- no --> R404["404 (no tenant leak)"]
    MEM -- yes --> PERM{"Role grants action?<br/>e.g. devices:write"}
    PERM -- no --> R403["403"]
    PERM -- yes --> REPO["Tenant-scoped repository<br/>WHERE org_id = :org_id"]
    DEV --> OWN{"Writing own device?"}
    OWN -- no --> R403
    OWN -- yes --> RATE{"Within rate limit?"}
    RATE -- no --> R429["429 + Retry-After"]
    RATE -- yes --> REPO
```

| Concern | Control |
|---|---|
| Password storage | Argon2id via `pwdlib`. Unknown-email logins verify a dummy hash to prevent user enumeration through timing |
| Access tokens | 15-minute JWT with `sub`, `exp`, `iat`, `jti` |
| Refresh tokens | 256-bit random, stored as hashes, rotated on use, family revoked on reuse |
| Device keys | `tsl_live_<prefix>.<secret>`: 8-char lookup prefix in plaintext, 256-bit secret stored as SHA-256, shown once, two active keys allow zero-downtime rotation |
| Authorization | Roles `owner` › `admin` › `member` › `viewer`, mapped to actions in a code-level permission table, verified by a role × action test matrix |
| Rate limiting | Fixed-window counters in Redis (atomic `INCR` + `EXPIRE` pipeline), per device and per org |
| Redis outage | **Fail open** for ingestion (availability of telemetry), **fail closed** for login (brute-force protection) |
| Webhooks | Standard Webhooks HMAC-SHA256 signing, HTTPS only outside development, private/loopback/link-local IPs rejected at registration *and* send time, redirects not followed |
| Secrets in logs | `Authorization`, `X-Device-Key` and webhook secrets are redacted by the log processor |
| Containers | Multi-stage image, runs as a non-root user, dev ports bound to `127.0.0.1` |

---

## Capacity and performance

### Design target (back-of-envelope)

| Input | Value |
|---|---|
| Organizations × devices | 1,000 × 25 = **25,000 devices** |
| Sampling | 1 reading/min per device, uploaded in batches every 5 min |
| Request rate | 25,000 / 300 s ≈ **83 req/s** |
| Row rate | 25,000 / 60 s ≈ **417 rows/s** |
| Daily volume | ≈ **36M rows/day**, ≈ 2.5 GB/day at ~70 B/row with index |

At this rate a single, well-indexed Postgres handles writes comfortably once readings are batched. **Table growth, not throughput, is the first scaling ceiling**, which is why time-based partitioning and retention lead the [roadmap](#roadmap).

### Service-level objectives

| SLO | Target |
|---|---|
| Ingestion latency | p95 < 200 ms at 100 req/s |
| Duplicate readings | 0 under retries and concurrent replays |
| Cross-tenant reads | 0, enforced by tests on every resource type |
| Alert-to-webhook latency | < 60 s |

### Measured results 🚧 pending

Load tests are run with [Locust](https://locust.io/) (`load/locustfile.py`) simulating devices that post batches with idempotency keys.

| Load (req/s) | p50 | p95 | p99 | Error rate | Notes |
|---|---|---|---|---|---|
| — | — | — | — | — | Baseline |
| — | — | — | — | — | After first bottleneck fix |

---

## Tech stack

| Area | Choice | Why |
|---|---|---|
| Language | Python 3.12, managed with [uv](https://docs.astral.sh/uv/) | One tool for interpreter, venv and lockfile; reproducible installs |
| Web framework | FastAPI (async) | I/O-bound workload; types drive validation and OpenAPI |
| Validation | Pydantic v2, `pydantic-settings` | Discriminated unions per metric; config from the environment |
| Database | PostgreSQL 17, SQLAlchemy 2 (async) + asyncpg | Transactions, constraints, `SKIP LOCKED`; one engine for data and queue |
| Migrations | Alembic | Reviewed, versioned schema changes |
| Cache / limits | Redis 7 | Atomic counters and TTLs shared across API instances |
| Auth | PyJWT, `pwdlib[argon2]` | Stateless access tokens; memory-hard password hashing |
| HTTP client | httpx | Async, shared client created in the app lifespan |
| Observability | structlog, prometheus-client | JSON logs with request IDs; latency histograms and outbox lag |
| Testing | pytest, Testcontainers, respx, anyio | Real Postgres in tests; mocked upstream HTTP |
| Load testing | Locust | Device-shaped traffic with idempotency keys |
| Quality | Ruff, pre-commit, GitHub Actions | Lint and format locally and in CI; protected `main` |

---

## Quickstart

**Prerequisites:** Docker with Compose v2. For local development, also [uv](https://docs.astral.sh/uv/).

### Run the whole system

```bash
git clone https://github.com/sdukea/tessel.git
```

```bash
cd tessel && cp .env.example .env
```

```bash
docker compose up --build
```

Compose starts `db` and `redis`, runs a one-shot `migrate` service (`alembic upgrade head`), then starts `api` and `worker` from the same image once migrations succeed.

```mermaid
flowchart LR
    db[("db")] --> migrate["migrate<br/>(one-shot)"]
    redis[("redis")] --> api
    migrate -- "completed successfully" --> api["api"]
    migrate -- "completed successfully" --> worker["worker"]
```

- API docs: <http://localhost:8000/docs>
- Readiness: <http://localhost:8000/ready>
- Metrics: <http://localhost:8000/metrics>

### Local development

```bash
docker compose -f compose.dev.yaml up -d
```

```bash
uv sync && uv run alembic upgrade head
```

```bash
uv run fastapi dev app/main.py
```

```bash
uv run python -m app.worker.main
```

---

## Configuration

All settings are read from environment variables via `pydantic-settings`. See [`.env.example`](.env.example).

| Variable | Description | Example |
|---|---|---|
| `DATABASE_URL` | Async Postgres DSN | `postgresql+asyncpg://tessel:tessel@localhost:5432/tessel` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `JWT_SECRET` | Signing key for access tokens | *(32+ random bytes)* |
| `ACCESS_TOKEN_TTL_MINUTES` | Access token lifetime | `15` |
| `DEVICE_RATE_LIMIT_PER_MIN` | Per-device request limit | `120` |
| `ORG_RATE_LIMIT_PER_MIN` | Per-org request limit | `3000` |
| `WEATHER_BASE_URL` | Weather provider base URL | `https://api.open-meteo.com/v1` |
| `ENVIRONMENT` | `development` relaxes HTTPS-only webhook URLs | `development` |

---

## Testing

```bash
uv run pytest -q --cov=app --cov-branch
```

The only prerequisite is a running Docker daemon. No database needs to be set up by hand.

```mermaid
flowchart TB
    subgraph Unit["tests/unit — no I/O, milliseconds"]
        U1["Domain rules and validation"]
        U2["Signing, backoff, breaker logic"]
    end
    subgraph Integration["tests/integration — real Postgres via Testcontainers"]
        I1["CRUD status codes + problem+json shape"]
        I2["Role × action permission matrix"]
        I3["Cross-tenant access for every resource"]
        I4["Concurrent idempotent replays"]
        I5["Refresh-token reuse detection"]
        I6["Outbox processed exactly once across two workers"]
        I7["Weather: retry, open circuit, stale cache (respx)"]
    end
    Unit --> Integration
```

- A session-scoped fixture starts `postgres:17` once and applies Alembic migrations.
- Each test runs inside a transaction that is rolled back, so tests are isolated and fast.
- The ASGI app is exercised in-process with `httpx.AsyncClient(transport=ASGITransport(app))`.
- **Why not SQLite?** It differs from Postgres on types, constraints and `ON CONFLICT` behavior, which are exactly the things these tests need to prove.

CI (`.github/workflows/ci.yml`) runs `ruff check`, `ruff format --check`, the full test suite and a `docker build` on every pull request. `main` is protected and requires a green run.

---

## Observability

| Signal | Implementation |
|---|---|
| Request correlation | `X-Request-ID` accepted or generated, stored in a context variable, returned as a header and copied into outbox events so a webhook can be traced back to the ingest request that caused it |
| Logs | structlog JSON with request ID, route, status and duration; secrets redacted |
| Metrics | Request counts and a per-route latency histogram; `outbox_lag_seconds` for background-work health |
| Health | `/health` (process alive) and `/ready` (Postgres and Redis reachable) |

---

## Project structure

```text
tessel/
├── app/
│   ├── main.py              # app factory, lifespan (shared clients, pools)
│   ├── api/v1/              # routers: auth, orgs, farms, devices,
│   │                        #   ingest, webhooks, advice
│   ├── core/                # config, security, errors, logging
│   ├── domain/              # pure Python: models, rules, ports
│   ├── infra/               # db, repositories, redis, weather client,
│   │                        #   webhook sender
│   └── worker/main.py       # outbox + delivery loop
├── migrations/              # Alembic
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
│   ├── BRD.md               # requirements, personas, capacity estimate
│   └── adr/                 # architecture decision records
├── load/locustfile.py
├── Dockerfile               # multi-stage, non-root
├── compose.yaml             # full system
├── compose.dev.yaml         # Postgres + Redis for local dev
└── .github/workflows/ci.yml
```

---

## Design decisions

Each significant choice is recorded as an ADR in [`docs/adr/`](docs/adr/) with its context, decision and consequences.

| # | Decision | Trade-off accepted |
|---|---|---|
| 1 | **FastAPI, async**: the workload is I/O-bound on Postgres, Redis and HTTP | Fewer built-ins than Django; blocking calls in async routes must be avoided |
| 2 | **PostgreSQL for data, time series and the job queue** | One database is one scaling ceiling; next steps are partitioning, read replicas, then a dedicated time-series store |
| 3 | **Redis for rate limits and caching** | Another system to operate; explicit fail-open / fail-closed policy per route |
| 4 | **JWT + rotating refresh tokens** for people | Access tokens cannot be revoked early, so their lifetime is kept to 15 minutes |
| 5 | **Hashed API keys** for devices | Keys live on stealable hardware, so revocation and two-key rotation are required |
| 6 | **Tenant in the URL, tenant-scoped repositories** | Longer URLs and an extra lookup per request; Postgres RLS would add a second layer |
| 7 | **Idempotency keys** on ingestion | An extra write per batch plus a cleanup job for expired keys |
| 8 | **Transactional outbox** instead of Celery or Kafka | Polling adds a little latency and Postgres carries queue load; Kafka pays off at much higher throughput or many consumers |
| 9 | **Standard Webhooks signing** | Shared-secret HMAC means both sides hold the secret; asymmetric signatures would avoid that |
| 10 | **Real Postgres in tests** via Testcontainers | A few seconds of start-up; Docker is required in CI |
| 11 | **Keyset pagination** for readings | No random access to page N, only next and previous |
| 12 | **RFC 9457 problem details** for errors | Slightly more verbose than a bare message string |

---

## Known limitations

These are deliberate scope choices for the current scale, each with a known next step:

- **Single Postgres primary.** Fine for ~36M rows/day of writes; retention and partitioning are needed before storage becomes the bottleneck.
- **Fixed-window rate limiting** allows bursts of up to 2× the limit at window boundaries. A sliding window or token bucket would smooth this.
- **Polling worker.** Adds up to one poll interval of latency; `LISTEN/NOTIFY` could wake the worker immediately.
- **Shared-secret webhooks.** Receivers must protect the secret; asymmetric (Ed25519) signing is a possible upgrade.
- **Isolation is enforced in the application.** Postgres Row-Level Security would add defense in depth.

---

## Roadmap

```mermaid
flowchart LR
    M1["① Domain + REST contract<br/>validation, problem+json"] --> M2["② Persistence<br/>Postgres, migrations, tests"]
    M2 --> M3["③ Authenticated API<br/>JWT, device keys, RBAC"]
    M3 --> M4["④ Reliable ingestion<br/>idempotency, weather advice"]
    M4 --> M5["⑤ Async delivery<br/>outbox, worker, webhooks"]
    M5 --> M6["⑥ Production<br/>Docker, CI, observability, load tests"]
```

- [ ] Domain layer and versioned REST contract
- [ ] Pydantic trust boundary with per-metric validation
- [ ] PostgreSQL schema, Alembic migrations, keyset pagination
- [ ] Integration test suite on real Postgres
- [ ] User auth with refresh-token rotation
- [ ] Device API keys and Redis rate limiting
- [ ] Multi-tenant RBAC
- [ ] Idempotent ingestion
- [ ] Weather-backed irrigation advice with circuit breaker
- [ ] Transactional outbox and worker
- [ ] Signed webhooks with retries and SSRF protection
- [ ] Containerized deploy and CI
- [ ] Observability and published load-test results

**Beyond v1:** time-partitioned `readings` with retention policies, Postgres Row-Level Security, `LISTEN/NOTIFY` worker wake-ups, and a dedicated time-series store once write volume justifies it.

---

## Contributing

- Branch from `main` as `feat/…` or `fix/…` and open a pull request; CI must pass before merge.
- Commits follow [Conventional Commits](https://www.conventionalcommits.org/), e.g. `feat(ingest): idempotency keys`.
- Install hooks once with `uv run pre-commit install`; Ruff runs on every commit.
- Significant design choices get an ADR in `docs/adr/`.
