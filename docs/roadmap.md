# Tessel roadmap

Where each video in the playlist lands in Tessel.

Day 1, Video 1: Roadmap
A command-line tool with one command per process (serve, worker, simulate, migrate, loadtest), so the whole system is mapped before any of it exists.

Day 2, Video 2: Path of a backend engineer
The alert rules (dry, spike, stuck, silent) as plain functions, checked against real weather data so they don't raise false alarms.

Day 3, Video 3: What is a backend
A web server built directly on a socket, reading and writing HTTP by hand, to see what frameworks do for you.

Day 4, Video 4: Why first principles
Fake soil probes that replay real weather history and sometimes lose the server's reply, so retries can be tested.

Day 5, Video 5: HTTP
Correct status codes, CORS for browsers, and ETags so clients can skip downloading data that hasn't changed.

Day 6, Video 6: Routing
The real API in FastAPI, with versioned routes and one consistent error format.

Day 7, Video 7: Serialization
Readings sent out as clean JSON, with units and UTC timestamps.

Day 8, Video 8: Auth
Passwords and login tokens for people, secret keys for probes, and roles per organization.

Day 9, Video 9: Validation
Incoming readings checked and cleaned before they're stored.

Day 10, Video 10: Controllers, services, repositories
The code split into layers, and safe retries: a batch sent twice is stored once.

Day 11, Video 11: REST API design
An endpoint that lists a device's readings page by page.

Day 12, Video 12: Databases
Postgres tables, migrations, and storing each batch exactly once even under concurrent retries.

Day 13, Video 13: Caching
A cache for each device's latest reading, so the dashboard doesn't hit the database every time.

Day 14, Video 14: Task queues
A job queue in Postgres, so alerts are created with the readings and delivered in the background.

Day 15, Video 15: Full-text search
Searching technicians' field notes by word, ranked by relevance.

Day 16, Video 16: Error handling
Retries, a circuit breaker and a fallback, so a failing weather API doesn't take Tessel down.

Day 17, Video 17: Configuration
Settings read from the environment, and a refusal to start if they're wrong.

Day 18, Video 18: Observability
Structured logs and latency metrics, so you can see what Tessel is doing.

Day 19, Video 19: Graceful shutdown
A worker that finishes its current job before stopping.

Day 20, Video 20: Security
Rate limits for misbehaving probes, security headers, and protection against password guessing.

Day 21, Video 21.1: Scaling, part 1
Estimating the load (about 83 uploads a second) and measuring latency properly.

Day 22, Video 21.2: Scaling, part 2
A load test that checks for duplicates, and readings split into monthly tables.

Day 23, Video 22: Concurrency
Many network calls at once without overloading the other side, and heavy work moved off the main thread.

Day 24, Video 23: Object storage, part 1
CSV exports saved in object storage and downloaded through short-lived links.

Day 25, Video 24: Object storage, part 2
Very large files uploaded in parts, and downloads that can resume.

Day 26, Video 25: Real-time
Alerts pushed live to the dashboard.

Day 27, Video 26: Testing
Tools that make tests short: a fake clock, data builders, and a ready-made app.

Day 28, Video 27: Twelve-Factor App
Admin commands and a real worker process, all configured the same way.

Day 29, Video 28: OpenAPI
A check that fails the build if an API change would break existing clients.

Day 30, Video 29: Webhooks
Alerts sent to other systems, signed so they can be trusted.

Day 31, Video 30: DevOps
Docker images, a local stack with every service, and CI that tests every change.
