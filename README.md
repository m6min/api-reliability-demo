# API Reliability Demo

I built this project to put things I had learned in theory into practice: caching, rate limiting, authentication, and handling failures. I kept the API simple on purpose. Products gave me something familiar to read and update while I focused on how the backend behaves.

My main goal was to learn how load-testing tools work: how Locust generates requests, how user count and pacing affect the load, and how to read response times, percentiles, throughput, and failures. Comparing cache ON and OFF gave me a practical experiment to learn from.

**This is a learning and experimentation project.** I built it to try backend concepts and understand measurements on my own laptop. I did not design or validate it as a production service, and the results are not a promise about how it would perform with real users or on a different server.

**Start with the visual docs instead of boring plain text:** [Benchmark report](https://m6min.github.io/api-reliability-demo/) · [What I put into practice](https://m6min.github.io/api-reliability-demo/implementation.html)

The report uses saved measurements. It does not send traffic to a live API. The backend is intended to run locally; the same docs can also be [served locally](#view-the-docs-locally).

## What is in the project?

- Product CRUD with FastAPI, Pydantic, async SQLAlchemy, and PostgreSQL.
- Alembic migrations and a router / service / repository structure.
- Redis cache-aside for the product list, with TTL and invalidation after successful writes.
- IP-based fixed-window rate limiting using an atomic Redis Lua script.
- JWT login, Argon2 password hashing, and admin-only product writes.
- Different Redis failure policies: product reads continue; login and registration return 503 when their limiter cannot be checked.
- Request timing, cache HIT/MISS/ERROR logs, pytest tests, and a GitHub Actions test workflow.
- Docker Compose for the API, PostgreSQL, and Redis.

The [implementation page](https://m6min.github.io/api-reliability-demo/implementation.html) explains the decisions in short cards, including dummy password verification, cache invalidation, and the limits of each approach.

## Tech stack

| Part | Tools |
| --- | --- |
| API | Python 3.13, FastAPI, Pydantic |
| Database | PostgreSQL 16, SQLAlchemy async, asyncpg, Alembic |
| Cache and counters | Redis 7, redis-py |
| Authentication | PyJWT, pwdlib |
| Testing and measurements | pytest, pytest-asyncio, Locust |
| Environment and automation | uv, Docker Compose, GitHub Actions |
| Visual docs | HTML, CSS, JavaScript, SVG charts |

```text
Client → FastAPI router → Service → Repository → PostgreSQL
              │              │
              │              └── Redis product-list cache
              └── Redis rate-limit counter
```

## A result I measured

For the **500-product dataset**, these are the medians of three runs per mode:

| Metric | Cache OFF | Cache ON |
| --- | ---: | ---: |
| Average response time | 514.80 ms | 192.52 ms |
| P95 response time | 600 ms | 230 ms |
| Requests per second | 96.63 | 257.88 |
| Failed requests | 0 in all three runs | 0 in all three runs |

Each run used 50 Locust users, one API worker, and a 60-second duration. The target was 500 requests/s, but users waited for responses, so actual throughput could be lower. The sequence was OFF, ON, ON, OFF, OFF, ON, with warm-up requests before each run.

I ran these experiments on my own Ryzen 7 5700U laptop. The API, Locust, PostgreSQL, and Redis all shared the same machine, so the load generator and the application competed for its resources. This was not a test with a separate load generator and a dedicated production server.

The numbers help me compare two configurations under this particular workload. They do not establish a maximum user capacity or predict response times on a cloud deployment. The workload repeatedly reads a product list; it does not represent the full mix of reads, writes, logins, and network conditions of a real application. Zero failures during these short runs also does not prove long-term reliability.

I did not measure SQL query counts or per-container CPU load. The reported P95 is the median of three run-level P95 values, not a percentile calculated from all requests combined. The measurements were recorded on 23 November 2026, before later auth and logging changes. My aim was to learn how to set up, compare, and interpret experiments, not to publish a production performance guarantee.

[Explore the charts](https://m6min.github.io/api-reliability-demo/) or inspect the [recorded JSON](docs/data/products-500/results.json).

## Run locally

It's not hard to test this project yourself as it seems. Follow the steps below.
And a note: these instructions set up the local demo for exploring the API and running experiments. The Compose configuration is a development setup, not a production deployment guide.

### 1. Get the project

Install [Docker Desktop](https://docs.docker.com/get-started/get-docker/) and start it. On Linux, Docker Engine with the Compose plugin also works. You do not need to install PostgreSQL or Redis separately.

```sh
git clone https://github.com/m6min/api-reliability-demo.git
cd api-reliability-demo
```

### 2. Create your environment file

Copy `.env.example` to `.env` in the project root. If `.env` already exists, edit it instead of overwriting it.

PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS / Linux:

```sh
cp .env.example .env
```

Set `POSTGRES_PASSWORD` to a local password. For this demo's connection-string builder, use letters and digits to avoid URL-escaping issues.

Replace the **entire** `JWT_SECRET_KEY` value with a generated key. The text in `.env.example` is a reminder, not a command that runs automatically. You can generate a key using Docker, without installing Python locally:

```sh
docker run --rm python:3.13-slim-bookworm python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the output after `JWT_SECRET_KEY=`. Of course do not commit `.env`.

The remaining defaults work for a fresh local setup. If PostgreSQL's host port is unavailable, change `POSTGRES_PORT` to `15432`. If port 8000 is busy, add `API_PORT=8001`. Compose uses the internal addresses `db:5432` and `redis:6379` for the API automatically.

### 3. Start everything

```sh
docker compose up -d --build
docker compose ps
```

The API waits for PostgreSQL and Redis, then runs `alembic upgrade head` automatically before Uvicorn starts.
**Note:** The first build can take longer because it downloads images and dependencies.

Open [Swagger](http://localhost:8000/docs). Use your chosen API port instead of 8000 if you changed it. A fresh database has no products, so an empty list is expected.

### 4. Try authentication and product writes

1. Register through `POST /api/auth/register` with an email and a password of 15–128 characters.
2. Log in through `POST /api/auth/login`.
3. Copy `access_token` into Swagger's **Authorize** box, without adding `Bearer` yourself.
4. Try `GET /api/users/me`.

Product reads are public. Creating, updating, and deleting products requires an admin account. To grant this locally, open PostgreSQL using the user and database from your `.env`. With the example defaults:

```sh
docker compose exec db psql -U api_user -d api_reliability
```

Replace the email below with the account you registered:

```sql
UPDATE users
SET is_admin = true
WHERE email = 'your-email@example.com'
RETURNING id, email, is_admin;
```

`UPDATE 1` means the account was updated. `UPDATE 0` means the email did not match. Exit psql with `\q`. There is no public endpoint for granting admin access.

### Everyday commands

| Task | Command |
| --- | --- |
| Follow the last 30 API logs | `docker compose logs --tail 30 -f api` |
| Rebuild after code changes | `docker compose up -d --build api` |
| Stop the services | `docker compose stop` |
| Start them again | `docker compose up -d` |

`Ctrl+C` while following logs only stops the log viewer. PostgreSQL data lives in a named volume: ordinary `stop` and `down` preserve it, while **`docker compose down -v` deletes it**. Changing the PostgreSQL password in `.env` does not change an existing database user's password.

## Develop and run tests with uv

The Docker route above does not require a local uv installation. For editing, running tests, or using Locust, install [uv](https://docs.astral.sh/uv/getting-started/installation/).

Windows:

```powershell
winget install --id=astral-sh.uv -e
```

macOS / Linux:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Open a new terminal if `uv` is not found, then run from the project root:

```sh
uv python install 3.13
uv sync --locked --group dev
docker compose up -d db redis
```

Create the separate test database once. Use your configured PostgreSQL user if it differs from `api_user`:

```sh
docker compose exec db createdb -U api_user api_reliability_test
uv run pytest -q
```

If the database already exists, skip `createdb`. **Repository tests drop and recreate tables inside `api_reliability_test`; do not store anything you want to keep there.** They do not target the application database. Redis behavior is mocked in the test suite.

To run only tests that do not need a running database:

```sh
uv run pytest -q --ignore=tests/test_product_repository.py
```

To run FastAPI directly on your computer instead of in its container:

```sh
docker compose stop api
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Keep `POSTGRES_HOST=localhost` and `REDIS_HOST=localhost` in `.env` for this mode, with the published host ports. Stop local Uvicorn before starting the API container on the same port.

The [test workflow](.github/workflows/tests.yml) runs pytest on pushes and pull requests, using its own temporary PostgreSQL service and test-only credentials. The [Actions tab](https://github.com/m6min/api-reliability-demo/actions) shows the actual run status.

## View the docs locally

After installing uv:

```sh
uv run python -m http.server 8080 --bind 127.0.0.1 --directory docs
```

Open [the report](http://localhost:8080/) or [the implementation notes](http://localhost:8080/implementation.html). Use HTTP instead of double-clicking the HTML file because the charts fetch JSON and CSV files. No running backend or database is needed to view them.

## Explore load testing

With the API running and uv dependencies installed:

```sh
uv run locust --host http://127.0.0.1:8000
```

Open [Locust](http://localhost:8089/). The default product-list rate limit is 10 requests per 60 seconds per IP, so a load test will quickly produce expected 429 responses. For a cache comparison, deliberately raise that limit in your local test configuration and restart the API; keep all other conditions comparable. Restore the limit afterward.

The [benchmark script](scripts/benchmark_verify.py) contains the repeated-run setup, including Redis database 15 and a raised rate limit. It refuses to overwrite existing `results.json` files. The [seed script](scripts/seed_benchmark.py) adds synthetic products until there are 500 and clears the list cache; it changes your local data, so it is not part of normal startup. Stored results belong to the recorded experiment, not every future version of this code.

## Current limits

The API has working authentication, permissions, tests, and failure handling, but those pieces alone do not make it production-ready. I have not validated this setup for real customer data, sustained production traffic, or operational recovery. A production version would need its own workload testing, security review, deployment configuration, a backup and recovery plan.

- The backend is a local experiment, not a hosted production API. The published docs display recorded results.
- Product lists are not paginated. Simultaneous misses and concurrent writes can still create cache consistency problems.
- A failed invalidation can leave old data until its TTL expires. Fail-open reads can increase database load during a Redis outage.
- Rate limiting uses the observed client IP. A real proxy deployment needs trusted proxy configuration; shared IPs share limits.
- Access tokens expire, but there are no refresh tokens or immediate logout revocation.
- Dummy hash verification reduces one account-existence timing difference; it is not a constant-time guarantee. Registration still reports duplicate emails.
- The API health check verifies an HTTP response, not ongoing readiness of every dependency.

I kept these limits visible because understanding what the implementation does not guarantee is part of what I wanted to learn.
