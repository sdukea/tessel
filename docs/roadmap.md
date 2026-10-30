# Tessel roadmap

One row per video in Sriniously's *Backend from first principles* playlist (31 videos), the
Tessel feature it drives, and the day it's built. Source: the Tessel Backend Build study page.

| Day | Video | Tessel feature it drives |
|---|---|---|
| 1 | 1. Roadmap for backend from first principles | **Map the system:** a CLI with one sub-command per process (`serve`, `worker`, `simulate`, `migrate`, `loadtest`) |
| 2 | 2. Walk the path of a true backend engineer | **The domain core:** pure alert rules (dry, spike, stuck, silent) tested on real weather data |
| 3 | 3. What is a Backend, how do they work and why do we need them? | **A server from a socket:** HTTP/1.1 framed by hand over TCP, with a readings endpoint |
| 4 | 4. Benefits of learning backend engineering from first principles | **A fleet of fake probes:** real ERA5-Land history replayed over a link that loses responses |
| 5 | 5. Understanding HTTP for backend engineers | **HTTP semantics, by hand:** 405 with `Allow`, CORS preflight, content negotiation, ETag/304 |
| 6 | 6. What is Routing in Backend? | **Routing and errors:** versioned FastAPI router, typed path parameters, problem+json errors |
| 7 | 7. Serialization and Deserialization for backend engineers | **Response models:** units on every value, UTC timestamps, rounded floats |
| 8 | 8. Authentication and authorization for backend engineers | **Auth for people and probes:** Argon2id, JWTs, rotating refresh tokens, hashed device keys, org roles |
| 9 | 9. Validations and transformations for backend engineers | **Validate at the edge:** ingest batches checked, converted and normalised before storage |
| 10 | 10. Controllers, services, repositories, middlewares and request context | **Layers and idempotency:** handler → service → repository, request IDs, idempotency keys |
| 11 | 11. Complete REST API Design | **REST resources and pagination:** nested org/device resources with keyset cursors |
| 12 | 12. Mastering Databases with Postgres | **Postgres, exactly once:** schema, constraints, migrations, idempotent ingestion |
| 13 | 13. Caching, the secret behind it all | **Cache the hottest query:** cache-aside, generational invalidation, stampede lock |
| 14 | 14. Task queues and background jobs | **Alerts through an outbox:** Postgres job queue with `SKIP LOCKED`, leases and backoff |
| 15 | 15. Full text search using Elasticsearch | **Search field notes:** Postgres full-text search with a GIN index, ranking and snippets |
| 16 | 16. Error Handling and Building Fault Tolerant Systems | **Survive the weather API:** retries with jitter, circuit breaker, stale fallback |
| 17 | 17. Production-grade Configuration Management | **Config that fails fast:** typed settings that refuse to start when wrong |
| 18 | 18. Logging, Monitoring and Observability | **See what it's doing:** JSON logs with redaction, latency histogram, `/metrics` |
| 19 | 19. Graceful Shutdown | **Stop without losing work:** a worker that finishes its current job on SIGTERM |
| 20 | 20. Backend Security: Everything You Need to Know | **Security controls:** token-bucket rate limiting, security headers, login throttling |
| 21 | 21.1 Backend Scaling and Performance Engineering: Part 1 | **Estimate, then measure:** capacity maths, percentiles, the N+1 fix |
| 22 | 21.2 Backend Scaling and Performance Engineering: Part 2 | **Load test and partitions:** async load test with zero duplicates, monthly partitions |
| 23 | 22. Concurrency & Parallelism: IO Bound vs CPU Bound | **I/O-bound vs CPU-bound:** bounded async fetches, CPU work in a process pool |
| 24 | 23. Object Storage: Part 1 | **Exports via presigned URLs:** safe keys, SigV4 signing, two-phase records |
| 25 | 24. Object Storage: Part 2 | **Multipart and ranges:** part sizing within S3's limits, resumable downloads |
| 26 | 25. Real-Time Backends | **Live alerts over SSE:** per-org channels, Last-Event-ID replay, heartbeats |
| 27 | 26. Testing for Backend Engineers | **Failure tests:** fake clock, factories, app harness, property tests |
| 28 | 27. The Twelve-Factor App | **Admin processes:** admin CLI, Procfile, a real worker process |
| 29 | 28. OpenAPI: The universal contract | **The contract in CI:** committed `openapi.json` and a breaking-change check |
| 30 | 29. Webhooks: how the server calls you | **Signed webhooks:** Standard Webhooks signatures, SSRF guard, retry schedule |
| 31 | 30. DevOps for backend engineers | **Ship it:** Dockerfile, Compose stack, CI with real Postgres and an image scan |
