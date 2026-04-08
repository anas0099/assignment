# Bing Scraper

Live app: https://bing-scraper-prod-3fce2e7ea328.herokuapp.com

This project is a web app that lets authenticated users upload a list of keywords and automatically scrape Bing search results for each one. For every keyword, it stores:

- Total number of Bing Ads on the page
- Total number of links
- Full raw HTML of the results page

The system is built to handle large batches reliably, with resilience against Bing's rate limits and anti-automation measures.

---

## What this app actually does

Users sign up, log in, and upload a CSV file with up to 100 keywords.

Once uploaded:
- Each keyword is stored and pushed to Kafka
- Workers start scraping Bing in the background
- Results appear in the UI as each keyword completes

Each keyword has its own detail page showing:
- Ads count
- Link count
- Collapsible raw HTML viewer with a copy button

---

## Search functionality

Users can search and filter across all uploaded keywords from the keyword list page.

- Keyword-based search filters results in real time
- Status filters (All, Pending, Processing, Completed, Failed) let users focus on specific states
- For larger datasets this can be optimized with PostgreSQL full-text search indexes (`GIN` on `tsvector`) which are already supported by the existing database

---

## User experience and system feedback

The system communicates clearly at every stage so users always know what is happening.

- Keywords show their current status: `pending`, `processing`, `completed`, or `failed`
- Results appear incrementally as scraping finishes - no need to wait for the full batch
- Failed keywords are retried automatically with exponential backoff; after 5 attempts they are marked permanently failed with an error message visible in the UI
- Upload errors (duplicate file, rate limit hit, malformed CSV, oversized file) show an inline message immediately so the user knows exactly what went wrong
- The keyword list updates as statuses change, giving a live view of batch progress

This makes the experience feel responsive even though all scraping runs asynchronously in the background.

---

## How it works internally

When a CSV is uploaded:
1. The file is hashed (SHA256) to detect duplicates within a 5-minute window
2. Each keyword is validated, stored with status `pending`, and pushed to a Kafka topic
3. The upload view returns immediately - no waiting for scraping

On the worker side:
- A Kafka consumer reads messages from the topic
- Each message is handed off to a `ThreadPoolExecutor`
- Each thread opens a Chrome browser, scrapes Bing, and saves results

The scraper:
- Uses `undetected-chromedriver` to reduce bot detection
- Waits for the full page to render before extracting content
- Rotates user agents across requests
- Detects captcha pages and language-selection pages and retries

If a scrape fails:
- Retry count is incremented and the keyword is marked `failed`
- A background sweep thread re-queues failed keywords using exponential backoff (30s, 60s, 120s, 240s, 480s)
- After 5 total attempts the keyword is permanently failed

---

## Tech stack

- **Django 6** - Web app and REST APIs
- **PostgreSQL** - Main database, partitioned weekly
- **Kafka** - Message queue between web and workers
- **Redis** - Caching, sessions, rate limiting, deduplication
- **Selenium + undetected-chromedriver** - Scraping engine

---

## API

REST API endpoints are available alongside the web UI.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/signup/` | Create an account |
| POST | `/api/auth/login/` | Sign in and get token |
| GET | `/api/keywords/` | List keywords (supports search and status filter) |
| POST | `/api/keywords/upload/` | Upload a CSV file |
| GET | `/api/keywords/{id}/` | Get search result for a keyword |
| GET | `/api/keywords/{id}/status/` | Poll status for a keyword |

All endpoints except signup and login require a token in the `Authorization: Token <token>` header. Accounts are created via the web UI or the signup API endpoint.

---

## Testing

Tests are written with `pytest` and run without any external services. SQLite in-memory replaces PostgreSQL and Django's `LocMemCache` replaces Redis in the test environment. Kafka is fully mocked.

```bash
python -m pytest tests/ -v
```

Coverage focuses on the critical paths:

- **Auth** - signup, login, token validation, protected endpoints
- **Upload flow** - CSV parsing, keyword creation, Kafka dispatch, deduplication, rate limiting
- **Scraper** - HTML parsing, ad selector logic, retry and failure handling
- **Caching** - cache hit/miss, per-user isolation, invalidation on status change
- **Models** - default values, cascade deletes, relationships

CI runs the same suite on every push via GitHub Actions.

---

## Trade-offs and decisions

This challenge is intentionally scoped around trade-offs. Here is what was prioritized and why:

**Selenium over HTTP scraping**
A real browser was used because Bing actively blocks headless HTTP clients. Selenium with `undetected-chromedriver` was chosen to ensure the scraper actually works rather than getting blocked immediately. The cost is higher memory and slower throughput per worker.

**Kafka over a simpler queue**
Kafka was introduced to decouple the upload request from the scraping work. This means the web process returns immediately, keywords are never lost if the worker crashes, and the system can scale horizontally by adding more consumer processes without any code changes.

**Full HTML stored in the database**
For simplicity, raw HTML is stored in PostgreSQL. The plan for scale is to move it to object storage (S3) and store only a reference URL in the database. This change is isolated to the scraper engine and does not affect the rest of the system.

**Weekly table partitioning**
PostgreSQL declarative range partitioning is applied to both the `Keyword` and `SearchResult` tables. This keeps query performance stable as data grows and allows old partitions to be dropped instantly without any locking.

**Exponential backoff over immediate retry**
Retrying failed keywords immediately would hammer Bing and likely trigger more rate limiting. Backoff gives Bing's defenses time to reset while still eventually completing the batch.

**9 threads per dyno on Heroku**
The Heroku Basic plan limits us to one dyno per process type. To maximize throughput within that constraint, the worker runs 9 threads in parallel. The architecture already supports scaling to multiple dynos on higher plans - only the `SCRAPER_WORKERS` env var and dyno count need to change.

**Monetary constraints on production features**
S3 for raw HTML storage, Prometheus/Grafana for metrics, and multiple worker dynos were not integrated due to cost. The architecture is designed so all three can be added independently -  S3 is isolated to one function in the scraper engine, Prometheus hooks are stubbed in `apps/scraper/monitoring.py`, and additional worker dynos require only a Heroku plan upgrade with no code changes.

---

## Observability

- Every scrape attempt is logged with keyword ID, status, retry count, and error message
- Sweep thread activity (re-queued keywords, cycle errors) is logged separately
- Kafka consumer logs show message consumption and commit activity
- Failed keywords surface directly in the UI with the last error message
- A monitoring stub (`apps/scraper/monitoring.py`) is in place for connecting to Sentry or another error tracker - currently logs to stdout

Local logs:

```bash
docker compose logs -f kafka-consumer
```

Heroku logs:

```bash
heroku logs --tail --dyno worker
```

---

## Kafka

Topic name: `keyword-scrape`, Partitions: `18`

Kafka allows one consumer per partition, so the maximum number of parallel consumer processes is 18. With 3 worker dynos each gets 6 partitions, and with multiple threads per dyno concurrency scales further.

Messages are committed only after a keyword is successfully processed. If the worker crashes mid-batch, Kafka replays the uncommitted messages on restart so nothing is lost.

Cloud deployments connect to Confluent Cloud using SASL/SSL authentication via `KAFKA_SASL_USERNAME` and `KAFKA_SASL_PASSWORD`.

---

## Caching

Redis is used in three places:

**Keyword list (per user)**
- TTL: 30 seconds
- Invalidated immediately on upload or status change

**Search results (per keyword)**
- TTL: 5 minutes
- Results do not change once scraped so a longer TTL is safe

**Sessions**
- Using `cached_db` backend: Redis for fast reads, PostgreSQL as fallback
- Prevents CSRF errors if Redis restarts

---

## Rate limiting

**Scraper (global across all threads)**
- 30 requests per 60 seconds shared across all worker threads
- Prevents hammering Bing from a single IP

**Uploads (per user)**
- 10 uploads per hour, sliding window tracked in Redis
- UI shows how many minutes remain when the limit is hit

**Deduplication**
- Every uploaded file is hashed with SHA256
- Hash stored in Redis for 5 minutes
- Blocks accidental re-uploads of the same file within that window

---

## Database design

Both `Keyword` and `SearchResult` tables use PostgreSQL declarative range partitioning by `created_at` (weekly).

This means:
- Queries scan only the relevant week partition rather than the full table
- Old partitions can be dropped instantly without locking
- New partitions are created automatically on every deploy and pre-created 4 weeks ahead

---

## How scaling works

**Thread level**

Each worker runs a Kafka consumer with a `ThreadPoolExecutor`. `SCRAPER_WORKERS` controls how many threads run inside one process. At `SCRAPER_WORKERS=9`, nine keywords are scraped in parallel inside a single dyno.

**Dyno level**

Multiple worker dynos can be added on Heroku Standard or higher plans. Each dyno joins the same Kafka consumer group and Kafka automatically distributes partitions across them. With 18 partitions and 3 worker dynos, each handles 6 partitions - giving 27 concurrent scrapes at 9 threads per dyno.

**Database level**

Weekly partitioning keeps Postgres fast as data grows. Old partitions detach instantly with no table-level locking.

The real bottleneck is Bing response time and IP rate limiting, not compute.

---

## Why scraping is slow on Heroku

This is expected behavior, not a bug. The core reason is that we are opening a real Chrome browser for every keyword - not making a simple HTTP request. Chrome is a full GUI browser that consumes significant memory and CPU, and Heroku's Basic dynos have hard limits on both.

**RAM is the primary constraint**

The Heroku Basic dyno has 512MB of RAM. Each Chrome instance uses 80–150MB on its own. When multiple threads fire simultaneously, Chrome instances compete for the same limited memory. Under pressure, Chrome hangs waiting for resources and eventually hits the 120-second read timeout - meaning a single bad instance wastes 2 full minutes before the thread can retry. This is why some keywords take 2+ minutes even though most take 20–30 seconds.

We also observed `SessionNotCreatedException` errors - Chrome failing to start entirely due to memory pressure. The scraper catches these and retries, but it adds overhead.

**The 9 threads only help with large batches**

The thread pool is sized for 9 concurrent scrapes. However, if only 2 keywords are uploaded at a time, 7 threads sit idle. The throughput benefit of 9 threads is only visible when uploading 50–100 keywords at once, which fills the queue and keeps all threads busy continuously.

**Other contributing factors**

- **Shared CPU** - Basic dynos run on shared virtualized infrastructure. Chrome rendering is slower without dedicated compute
- **Forced render wait** - The scraper waits 8 seconds after page load for Bing's JavaScript to finish rendering. Every keyword pays this cost regardless of network speed
- **Datacenter IPs** - Bing does not serve ads to AWS datacenter IPs so `total_ads` will always be zero on Heroku. This is a Bing policy, not a scraper bug

**Local Docker is significantly faster**

When run locally with Docker using 3 consumer containers and 3 worker threads each, 9 keywords process simultaneously with stable Chrome performance. Local Docker has access to the full machine memory and CPU, so Chrome starts cleanly, pages render faster, and there are no timeout failures under normal conditions.

**Rough throughput comparison:**

| Environment | Throughput |
|---|---|
| Heroku Basic (1 dyno, 9 threads) | ~20 keywords/min, with occasional timeout delays |
| Local Docker (3 containers x 3 threads) | 9 keywords simultaneously, stable and fast |
| Dedicated machine (30+ threads) | Much higher, limited only by Bing rate limits |

In a real production setup the scraper worker would move to a dedicated machine with sufficient RAM to run many Chrome instances cleanly. The web app, database, Redis, and Kafka stay on managed services. This separation is already built into the architecture - the worker is a standalone process that only needs the Kafka bootstrap address and the database URL.

---

## Future improvements

- Move raw HTML storage to S3 and store only the object URL in the database
- Add proxy rotation to reduce IP-based rate limiting from Bing
- Add a scheduled partition maintenance job to run weekly rather than on deploy
- Expose Kafka consumer lag metrics for monitoring batch throughput

---

## Running locally with Docker

Docker and Docker Compose are required.

```bash
git clone https://github.com/anas0099/assignment
cd assignment
docker compose up -d
```

First startup takes a few minutes because the Chrome image needs to build. Once all containers are healthy, visit http://localhost:8000

Create a user:

```bash
docker compose exec web python manage.py createsuperuser
```

Watch scraper logs:

```bash
docker compose logs -f kafka-consumer
```

Stop everything:

```bash
docker compose down
```

---

## Environment variables

```bash
cp .env.example .env
```

For local development the defaults in `docker-compose.yml` work out of the box. For production the following variables need to be set:

```
SECRET_KEY
DATABASE_URL
REDIS_URL
KAFKA_BOOTSTRAP_SERVERS
KAFKA_SASL_USERNAME
KAFKA_SASL_PASSWORD
ALLOWED_HOSTS
DJANGO_SETTINGS_MODULE=config.settings.production
```

Tunable settings:

```
SCRAPER_WORKERS=9
UPLOAD_RATE_LIMIT_MAX=10
UPLOAD_RATE_WINDOW_SECONDS=3600
```

---

## Deploying to Heroku

The production app runs at https://bing-scraper-prod-3fce2e7ea328.herokuapp.com

The Heroku CLI needs to be installed and logged in.

Create the app and add-ons:

```bash
heroku create your-app-name --stack heroku-24
heroku addons:create heroku-postgresql:essential-0
heroku addons:create heroku-redis:mini
```

Add buildpacks:

```bash
heroku buildpacks:add heroku/python
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-chrome-for-testing
```

Set config vars:

```bash
heroku config:set DJANGO_SETTINGS_MODULE=config.settings.production
heroku config:set SECRET_KEY=your-secret-key
heroku config:set ALLOWED_HOSTS=your-app-name.herokuapp.com
heroku config:set KAFKA_BOOTSTRAP_SERVERS=your-bootstrap-server
heroku config:set KAFKA_SASL_USERNAME=your-api-key
heroku config:set KAFKA_SASL_PASSWORD=your-api-secret
heroku config:set CHROME_BINARY=/app/.chrome-for-testing/chrome-linux64/chrome
heroku config:set CHROMEDRIVER_PATH=/app/.chrome-for-testing/chromedriver-linux64/chromedriver
heroku config:set SCRAPING_MODE=async
heroku config:set SCRAPER_WORKERS=9
```

Deploy:

```bash
git push heroku main
heroku ps:scale web=1 worker=1
```

For Kafka, the app works with Confluent Cloud. Create a cluster, create a topic named `keyword-scrape` with 18 partitions, generate an API key, and use those credentials above.

---

## Project structure

```
apps/keywords/     models, views, API, services, dedup, rate limiting
apps/scraper/      scraping engine, Chrome utility, resilience, monitoring
kafka/             consumer process
config/            Django settings for local, test, and production
templates/         UI built with TailwindCSS
tests/             flat test directory, no external services required
```

---

## Screenshots

<img width="1728" height="768" alt="Screenshot 2026-04-07 at 10 40 11 PM" src="https://github.com/user-attachments/assets/91ef37fb-07db-4a35-95ac-6aeae2cf92ff" />

<img width="1721" height="563" alt="Screenshot 2026-04-07 at 10 45 56 PM" src="https://github.com/user-attachments/assets/55348fb3-ffce-4aa6-a6a4-104ec24f3942" />

<img width="1723" height="1117" alt="Screenshot 2026-04-07 at 10 40 49 PM" src="https://github.com/user-attachments/assets/8d4ab960-ba5e-45e4-af97-6693018ad441" />

<img width="1351" height="543" alt="Screenshot 2026-04-07 at 10 40 37 PM" src="https://github.com/user-attachments/assets/f9164b20-2320-4150-a65a-30edab29b104" />

<img width="1417" height="916" alt="Screenshot 2026-04-07 at 10 40 32 PM" src="https://github.com/user-attachments/assets/b896ce63-b79e-4e39-b4c2-b7df7db83820" />

<img width="1728" height="832" alt="Screenshot 2026-04-07 at 10 40 27 PM" src="https://github.com/user-attachments/assets/69fe8e5e-bd11-49d0-b4be-443dcef7e98a" />

<img width="1718" height="692" alt="Screenshot 2026-04-07 at 10 40 22 PM" src="https://github.com/user-attachments/assets/f9e74f19-201d-4e0a-b6e5-0026f59f7408" />

<img width="1728" height="741" alt="Screenshot 2026-04-07 at 10 40 14 PM" src="https://github.com/user-attachments/assets/f24ffbb1-174e-4212-bb99-f48ca0eabb9f" />
