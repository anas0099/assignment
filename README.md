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

A default admin user is created automatically on first run with username admin and password admin123. You can also sign up as a new user from the UI.

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

Create your first user:

    heroku run python manage.py createsuperuser

For Kafka, the app works with Confluent Cloud. Create a cluster, create a topic named keyword-scrape with 18 partitions, generate an API key, and use those credentials in the config above.


## How the scraping works

When a CSV is uploaded the view parses each line, creates a Keyword record with status pending, and publishes the keyword ID to the Kafka topic. The worker process runs a Kafka consumer that reads these messages and dispatches them to a thread pool. Each thread calls the scraping function which opens a Chrome window, navigates to Bing, waits for results to render, extracts the ad count and link count, captures the full HTML, and saves everything to the database.

If a scrape fails the retry count is incremented and the keyword stays in failed state. A background sweep thread runs every 30 seconds and re-publishes any failed keywords that have not yet hit the retry limit, applying exponential backoff of 30, 60, 120, 240, and 480 seconds.


## Upload rules

The same CSV file cannot be uploaded twice within a 5 minute window. This is checked via a SHA256 hash of the file content stored in Redis. If a duplicate is detected the UI shows a warning and the upload is blocked.

There is also a rate limit of 10 uploads per hour per user. This uses a sliding window counter in Redis. When the limit is hit the UI shows how many minutes until the next upload is allowed.


## Database partitioning

Both the Keyword and SearchResult tables are partitioned by week in PostgreSQL. New partitions are created automatically on deploy via a management command. A scheduled service also runs weekly to pre-create future partitions four weeks ahead. Old partitions can be dropped without locking or affecting the rest of the data.


## Project structure

    apps/keywords/     models, views, API, services, dedup, rate limiting
    apps/scraper/      engine, utility (Chrome), resilience, constants, monitoring
    kafka/             consumer process
    config/            Django settings for local and production, Kafka config
    templates/         HTML templates using TailwindCSS
    tests/             flat test directory with shared fixtures
