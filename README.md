# BTC / HYPE Tracker

## Monitoring API

`monitoring.py` provides the FastAPI service, an in-memory demo API, a live
monitoring dashboard, and Prometheus metrics. It does not require PostgreSQL.

Install the requirements, then run from the `New1` directory:

```powershell
uvicorn monitoring:app --reload --port 8000
```

Open **http://localhost:8000** for the dashboard. The sample API is available
at `/health`, `/users`, and `/products`; `/simulate-error`,
`/simulate-timeout?delay=3`, and `/simulate-rate-limit` generate failure,
latency, and rate-limit signals. The rate-limit demo returns HTTP 429 after five
requests in one minute.

The dashboard tracks availability, request counts, response time, HTTP status
codes, failed-request percentage, recent failure events, and process uptime. It
refreshes every two seconds. `/metrics` exposes Prometheus metrics and
`/api/monitoring/summary` returns the dashboard data as JSON. `/docs` provides
interactive API documentation. The error-rate alert threshold defaults to 10%;
set `ALERT_ERROR_PERCENT` or `ALERT_LATENCY_MS` before starting the service to
change alert thresholds.

## Run with Docker Compose

From the `New1` directory, copy `.env.example` to `.env`, set your Grafana
password, then start the API, Prometheus, and Grafana:

```powershell
Copy-Item .env.example .env
# Edit .env and set GRAFANA_PASSWORD
docker compose up --build
```

Open `http://localhost:8000` for the API dashboard, `http://localhost:9090`
for Prometheus, and `http://localhost:3000` for Grafana. Prometheus scrapes
`/metrics` every five seconds and evaluates the configured alerts. To stop the
containers, run `docker compose down`.

## Prometheus alerts and notifications

Prometheus sends alerts to Alertmanager, available at `http://localhost:9093`.
The rules in `prometheus/alerts.yml` cover API downtime, `/health` probe
failures, p95 response time above 3 seconds, HTTP 500 responses, and a failure
rate above 5%.

To enable email and Slack notifications, edit `alertmanager/alertmanager.yml`
and replace its SMTP host, sender, username, password, recipient, Slack webhook,
and channel placeholders with your service details. Keep real credentials
private. Then apply the configuration:

```powershell
docker compose up -d --force-recreate alertmanager prometheus
```

Alert rules are visible in Prometheus at `http://localhost:9090/alerts`; delivery
and silences are managed in Alertmanager at `http://localhost:9093`.

The in-memory dashboard counters and event history reset when the process
restarts. Prometheus persists its time series in a Docker volume.
