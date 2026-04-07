# Bing Scraper

Live app: https://bing-scraper-prod-3fce2e7ea328.herokuapp.com

A web application that lets users upload a list of keywords and automatically scrapes Bing search results for each one. For every keyword it stores the total number of ads on the page, the total number of links, and the full raw HTML of the results page.

The app is built to handle large batches reliably. It uses Kafka to queue keywords as messages and a pool of worker threads to process them in parallel. Failed keywords are automatically retried up to five times with exponential backoff before being marked as permanently failed.


## What it does

Users sign up, log in, and upload a CSV file containing up to 100 keywords. The system reads the file, queues every keyword into Kafka, and starts scraping Bing in the background. Results appear in the UI as they come in. Each keyword page shows the ads count, link count, and a collapsible raw HTML viewer with a copy button.

The scraper uses a real Chrome browser under the hood via undetected-chromedriver, which helps avoid Bing bot detection. It waits for the page to fully render before reading the content, handles captcha detection, and rotates user agents across requests.


## Tech stack

Django 6 handles the web layer and REST API. PostgreSQL stores all data and is partitioned by week so old data can be dropped cleanly without affecting performance. Kafka is the message broker between the web app and the scraper workers. Redis handles caching for keyword lists and search results, session storage, rate limiting, and upload deduplication. Selenium with Chrome runs the actual scraping.


## Running locally with Docker

You need Docker and Docker Compose installed.

Clone the repo and start everything:

    git clone https://github.com/anas0099/assignment
    cd assignment
    docker compose up -d

The first startup takes a few minutes because it builds the Chrome image. Once all containers are healthy, visit http://localhost:8000

Sign up for a new account directly from the UI, or create a superuser with:

    docker compose exec web python manage.py createsuperuser

To watch the scraper logs:

    docker compose logs -f kafka-consumer

To stop everything:

    docker compose down


## Environment variables

Copy the example file and fill in your values:

    cp .env.example .env

For local development the defaults in docker-compose.yml work out of the box. For production you need to set at minimum:

    SECRET_KEY
    DATABASE_URL
    REDIS_URL
    KAFKA_BOOTSTRAP_SERVERS
    KAFKA_SASL_USERNAME
    KAFKA_SASL_PASSWORD
    ALLOWED_HOSTS
    DJANGO_SETTINGS_MODULE=config.settings.production

Rate limiting and worker count can be tuned with:

    SCRAPER_WORKERS=9
    UPLOAD_RATE_LIMIT_MAX=10
    UPLOAD_RATE_WINDOW_SECONDS=3600


## Running tests

Tests run against a real PostgreSQL and Redis. Use the Docker environment:

    docker compose exec web pytest tests/ -v --tb=short --cov=apps

Or on CI the GitHub Actions workflow handles this automatically on every push.


## Deploying to Heroku

The production app runs at https://bing-scraper-prod-3fce2e7ea328.herokuapp.com

The app is already configured for Heroku. You need the Heroku CLI installed and logged in.

Create the app and add-ons:

    heroku create your-app-name --stack heroku-24
    heroku addons:create heroku-postgresql:essential-0
    heroku addons:create heroku-redis:mini

Add the Chrome buildpack alongside Python:

    heroku buildpacks:add heroku/python
    heroku buildpacks:add https://github.com/heroku/heroku-buildpack-chrome-for-testing

Set environment variables:

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

Deploy:

    git push heroku main

Scale dynos:

    heroku ps:scale web=1 worker=1

For Kafka, the app works with Confluent Cloud. Create a cluster, create a topic named keyword-scrape with 18 partitions, generate an API key, and use those credentials in the config above.


## How the scraping works

When a CSV is uploaded the view parses each line, creates a Keyword record with status pending, and publishes the keyword ID to the Kafka topic. The worker process runs a Kafka consumer that reads these messages and dispatches them to a thread pool. Each thread calls the scraping function which opens a Chrome window, navigates to Bing, waits for results to render, extracts the ad count and link count, captures the full HTML, and saves everything to the database.

If a scrape fails the retry count is incremented and the keyword stays in failed state. A background sweep thread runs every 30 seconds and re-publishes any failed keywords that have not yet hit the retry limit, applying exponential backoff of 30, 60, 120, 240, and 480 seconds.


## Kafka

Kafka sits between the web app and the scraper workers. When a CSV is uploaded, the web process publishes one message per keyword to a topic called keyword-scrape. The consumer process on the worker dyno reads from this topic and dispatches each message to a thread in the pool.

The topic has 18 partitions. This matters because Kafka allows one consumer per partition at a time. With 18 partitions you can run up to 18 consumer processes in parallel across multiple machines, each taking their own slice of work, with no coordination needed between them.

Messages are committed to Kafka only after a keyword is successfully processed. If the worker crashes mid-batch, Kafka replays the uncommitted messages on restart so nothing is lost. For cloud deployments the app connects to Confluent Cloud using SASL/SSL authentication, configured via the KAFKA_SASL_USERNAME and KAFKA_SASL_PASSWORD environment variables.


## Caching

Redis is used in three places.

Keyword list pages are cached per user with a 30 second TTL. Each user has their own cache key so one user's data never leaks into another's view. The cache is invalidated immediately when a new upload happens or when a keyword status changes, so users always see fresh data after an action.

Individual search result pages are cached per keyword with a 5 minute TTL. Once a keyword is scraped the result does not change, so a longer TTL is fine here. The cache is invalidated if the keyword is re-scraped.

Sessions are stored in Redis using Django's cached_db backend. This means reads are fast because they hit Redis first, but the session data is also written to PostgreSQL as a backup. If Redis restarts the session is loaded from the database instead of being lost, which prevents the CSRF errors you would otherwise see after a container restart.


## Rate limiting

The scraper has a shared rate limiter across all worker threads. It uses a sliding window counter in Redis keyed to a single global scraper key. The limit is 30 requests per 60 seconds across all workers combined. Before starting each scrape a thread checks this counter and waits if the limit is reached. This prevents hammering Bing with too many requests at once.

CSV uploads are rate limited per user. The default is 10 uploads per hour, tracked with a sliding window in Redis. Each upload timestamp is stored in a list and timestamps outside the window are discarded before counting. When the limit is hit the UI shows an error message with how many minutes remain before the next upload is allowed. The limits are configurable via environment variables UPLOAD_RATE_LIMIT_MAX and UPLOAD_RATE_WINDOW_SECONDS.

Upload deduplication works separately from rate limiting. Every uploaded file is hashed with SHA256 and the hash is stored in Redis with a 5 minute TTL. If the same file is uploaded again within that window the upload is blocked and the user sees a warning message. This prevents accidental double uploads of the same CSV.


## How scaling works

At the thread level, each worker dyno runs a Kafka consumer with a ThreadPoolExecutor. The SCRAPER_WORKERS environment variable controls how many threads run inside one dyno. With SCRAPER_WORKERS=9, nine keywords are scraped in parallel inside a single process.

At the dyno level, you can run multiple worker dynos on Heroku Standard or higher plans. Each dyno is an independent Kafka consumer in the same consumer group. Kafka automatically assigns partitions across all consumers in the group. With 18 partitions and 3 worker dynos, each dyno handles 6 partitions. With 9 threads per dyno that is 27 concurrent scrapes total.

At the database level, the weekly partitioning means that as data grows Postgres only scans the relevant week partition rather than the full table. Old partitions can be detached and dropped instantly without locking anything.

The full theoretical ceiling with the current Kafka setup is 18 consumer processes times however many threads per process. In practice the bottleneck is Bing response time and whether the host IP gets rate limited, not compute capacity.


## Upload rules

The same CSV file cannot be uploaded twice within a 5 minute window. This is checked via a SHA256 hash of the file content stored in Redis. If a duplicate is detected the UI shows a warning and the upload is blocked.

There is also a rate limit of 10 uploads per hour per user. This uses a sliding window counter in Redis. When the limit is hit the UI shows how many minutes until the next upload is allowed.


## Database partitioning

Both the Keyword and SearchResult tables are partitioned by week in PostgreSQL. New partitions are created automatically on deploy via a management command. A scheduled service also runs weekly to pre-create future partitions four weeks ahead. Old partitions can be dropped without locking or affecting the rest of the data.


## Why scraping is slow on Heroku and what production would look like

On the Heroku deployment each keyword takes roughly 20 to 30 seconds to scrape. This is expected and is a consequence of how the Heroku environment works, not a bug in the code.

The main reasons for the slowness are:

Heroku Basic dynos have 512MB of RAM. Each Chrome instance consumes around 80 to 150MB on its own. With 9 worker threads running in parallel that is close to the memory ceiling, so Chrome instances run conservatively and any additional overhead causes slowdowns or restarts.

Heroku dynos are shared virtualized containers running on AWS. They do not have dedicated CPU. When multiple processes compete for CPU, Chrome rendering takes longer than it would on a dedicated machine.

The scraper waits 8 extra seconds after the page loads to allow Bing's JavaScript to finish rendering ads and results. This wait is necessary to get complete HTML but it means every single keyword adds at least 8 seconds of idle time regardless of how fast the network is.

Heroku's outbound IP addresses are from AWS data centers. Bing recognises datacenter IPs and does not serve ads to them. This does not slow down the scraping itself but means total_ads will always be zero on Heroku.

When tested locally on a MacBook with Docker, 3 consumer containers were run simultaneously with 3 worker threads each. That gave 9 keywords processing in parallel at the same time with stable throughput. Local Docker has access to the full machine memory and CPU which is why it performs significantly better than Heroku Basic dynos.

In a real production environment the scraper worker would run on a dedicated machine with multiple CPU cores and sufficient RAM. The web app, database, Redis, and Kafka would remain on managed cloud services. Only the worker process moves to the dedicated machine. This separation is already built into the architecture since the worker is a standalone process that only needs the Kafka bootstrap address and the database URL to operate independently.

A rough comparison of throughput:

On Heroku Basic with 9 threads in one dyno: roughly 20 keywords per minute due to shared CPU and memory constraints.

Locally with 3 Docker containers and 3 threads each: 9 keywords processed simultaneously, completing a batch of 9 in the same wall time as a single keyword on Heroku.

On a dedicated machine with more cores and memory: 30 or more threads can run in parallel with stable Chrome instances, giving much higher throughput than any shared hosting environment.


## Project structure

    apps/keywords/     models, views, API, services, dedup, rate limiting
    apps/scraper/      engine, utility (Chrome), resilience, constants, monitoring
    kafka/             consumer process
    config/            Django settings for local and production, Kafka config
    templates/         HTML templates using TailwindCSS
    tests/             flat test directory with shared fixtures

## Testing Screenshot

<img width="1728" height="768" alt="Screenshot 2026-04-07 at 10 40 11 PM" src="https://github.com/user-attachments/assets/91ef37fb-07db-4a35-95ac-6aeae2cf92ff" />

<img width="1721" height="563" alt="Screenshot 2026-04-07 at 10 45 56 PM" src="https://github.com/user-attachments/assets/55348fb3-ffce-4aa6-a6a4-104ec24f3942" />

<img width="1723" height="1117" alt="Screenshot 2026-04-07 at 10 40 49 PM" src="https://github.com/user-attachments/assets/8d4ab960-ba5e-45e4-af97-6693018ad441" />

<img width="1351" height="543" alt="Screenshot 2026-04-07 at 10 40 37 PM" src="https://github.com/user-attachments/assets/f9164b20-2320-4150-a65a-30edab29b104" />

<img width="1417" height="916" alt="Screenshot 2026-04-07 at 10 40 32 PM" src="https://github.com/user-attachments/assets/b896ce63-b79e-4e39-b4c2-b7df7db83820" />

<img width="1728" height="832" alt="Screenshot 2026-04-07 at 10 40 27 PM" src="https://github.com/user-attachments/assets/69fe8e5e-bd11-49d0-b4be-443dcef7e98a" />

<img width="1718" height="692" alt="Screenshot 2026-04-07 at 10 40 22 PM" src="https://github.com/user-attachments/assets/f9e74f19-201d-4e0a-b6e5-0026f59f7408" />

<img width="1728" height="741" alt="Screenshot 2026-04-07 at 10 40 14 PM" src="https://github.com/user-attachments/assets/f24ffbb1-174e-4212-bb99-f48ca0eabb9f" />
