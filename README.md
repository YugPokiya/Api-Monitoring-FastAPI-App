# FastAPI Monitoring Demo

This project runs a FastAPI sample service with Prometheus metrics, Grafana
dashboards, alert rules, and Alertmanager. The monitored API data is an in-memory
demo; the SQLAlchemy models in `models.py` and seeder in `Main3.py` are separate
from the monitoring service and require a PostgreSQL database if used.

## FastAPI setup

### Run locally

From this directory, install the service dependencies and start the API:

```powershell
python -m pip install -r requirements.txt
uvicorn monitoring:app --reload --port 8000
```

Visit `http://localhost:8000` for the API dashboard and `http://localhost:8000/docs`
for interactive API documentation. Useful endpoints:

| Endpoint | Purpose |
| --- | --- |
| `/health` | Health check; returns HTTP 200 while the API is available |
| `/users`, `/products` | Sample successful API responses |
| `/metrics` | Prometheus metrics endpoint |
| `/api/monitoring/summary` | In-memory monitoring summary, alerts, and recent events |

The process keeps request counts and recent event history in memory, so those
values reset when the API restarts.

### Run with Docker Compose

From this directory, create the environment file, replace the demo Grafana
password, and start the stack:

```powershell
Copy-Item .env.example .env
# Edit .env and set a private GRAFANA_PASSWORD.
docker compose up -d --build
docker compose ps
```

Services:

| Service | URL | Role |
| --- | --- | --- |
| FastAPI | `http://localhost:8000` | API and built-in dashboard |
| Prometheus | `http://localhost:9090` | Metrics, targets, and alert rule status |
| Grafana | `http://localhost:3000` | Provisioned monitoring dashboard |
| Alertmanager | `http://localhost:9093` | Alert grouping, routing, and silences |

Grafana defaults to username `admin`. Its password is `GRAFANA_PASSWORD` from
`.env`; without a `.env`, Compose uses the fallback `Abc123`. Change the demo
password before using this stack outside a local development machine.

Stop containers and remove the Compose network with `docker compose down`. This
preserves named data volumes. To also delete persisted Grafana, Prometheus, and
Alertmanager data, use `docker compose down -v` (this permanently removes those
volumes).

## Monitoring architecture

```text
Clients --HTTP--> FastAPI (:8000) --/metrics--> Prometheus (:9090)
                       |                            |
                       +-- /health <-- Blackbox      +-- alert rules --> Alertmanager (:9093)
                       |                            |
                       +-- API dashboard             +-- PromQL <-- Grafana (:3000)
```

Prometheus scrapes FastAPI every 5 seconds and also asks Blackbox Exporter to
probe `/health`. FastAPI request counters and latency histograms use bounded
route-template labels. Grafana queries Prometheus; its datasource URL is
`http://prometheus:9090` on the Compose network. Prometheus evaluates
`prometheus/alerts.yml` and sends firing alerts to Alertmanager.

The Compose volumes persist Prometheus, Grafana, and Alertmanager data. API
process logs are appended to `logs/api.log` on the host. The dashboard's request
history and events remain in memory and are not persisted.

## Dashboard configuration

Grafana provisions the Prometheus datasource from
`grafana/provisioning/datasources/prometheus.yml` and loads dashboards from
`grafana/provisioning/dashboards/provider.yml`. The JSON dashboard is
`grafana/dashboards/api-monitoring.json`.

After the stack is running, open Grafana and select **Dashboards > API Monitoring
> FastAPI Monitoring**. The dashboard includes API availability, request rate,
failed request rate, p95 latency, HTTP status rates, host CPU and memory,
uptime, and failed requests by endpoint. Generate some requests first; rate and
latency panels may be empty until Prometheus has scraped samples.

To check collection directly, open `http://localhost:9090/targets`. The
`fastapi` and `fastapi-health` targets should report **UP**. In Grafana's
**Explore > Prometheus**, useful queries include:

```promql
up{job="fastapi"}
sum by (path, status) (rate(api_http_requests_total[5m]))
histogram_quantile(0.95, sum by (le) (rate(api_http_request_duration_seconds_bucket[5m])))
```

## Alert rules

Rules are in `prometheus/alerts.yml` and their firing state is visible at
`http://localhost:9090/alerts`. They detect:

| Rule | Condition |
| --- | --- |
| `FastAPITargetDown` | Prometheus cannot scrape the API for 30 seconds |
| `FastAPIHealthCheckFailed` | Blackbox health probe fails for 30 seconds |
| `FastAPIResponseTimeOver3Seconds` | p95 latency exceeds 3 seconds for 1 minute |
| `FastAPIHttp500Errors` | HTTP 500s appear in the five-minute rate window for 30 seconds |
| `FastAPIAuthenticationFailures` | HTTP 401 responses are observed |
| `FastAPIRateLimitExceeded` | HTTP 429 responses are observed |
| `FastAPITimeout` | HTTP 504 responses are observed |
| `FastAPIIncreasedFailureRate` | 4xx/5xx rate exceeds 5% for 1 minute |

`ALERT_LATENCY_MS` (default `1000`) and `ALERT_ERROR_PERCENT` (default `10`)
configure alerts in the API's own `/api/monitoring/summary` response. These are
passed to the API container from `.env`; after changing them recreate the API:

```powershell
docker compose up -d --force-recreate api
```

The Prometheus p95 rule currently uses a separate fixed 3-second threshold.
Alertmanager is preconfigured with example email and Slack receiver values in
`alertmanager/alertmanager.yml`. Replace all placeholders with real service
settings before expecting notifications, and keep credentials private. Restart
Alertmanager to apply changes:

```powershell
docker compose restart alertmanager
```

## Failure simulation

These endpoints deliberately simulate failures for monitoring demonstrations;
they are not real authentication or traffic-control middleware. Open an endpoint
in a browser, or call it with an HTTP client, then inspect the built-in dashboard,
`/api/monitoring/summary`, Prometheus targets/alerts, and Grafana.

| Scenario | Request | Expected result |
| --- | --- | --- |
| Invalid authentication | `http://localhost:8000/simulate-auth` | HTTP 401, authentication cause, API alert |
| Timeout | `http://localhost:8000/simulate-timeout?delay=2` | If delay meets `ALERT_LATENCY_MS`, HTTP 504, timeout event and alert |
| Server error | `http://localhost:8000/simulate-error` | HTTP 500, captured failure cause and server error alert |
| Rate limit | Call `http://localhost:8000/simulate-rate-limit` six times within one minute | First five return HTTP 200; sixth returns HTTP 429 and rate limit alert |

Prometheus alert rules that use `rate()` need scrape samples and may take time to
fire according to their evaluation window and `for` duration. The API summary
alerts are available immediately after the simulated request.

## Troubleshooting

| Symptom | Checks and actions |
| --- | --- |
| `localhost:3000` does not open | Confirm Docker Desktop/Engine is running, then run `docker compose ps`. Check `docker compose logs --tail=100 grafana` and confirm port 3000 is not used by another process. |
| Grafana login fails | Use username `admin` and the `GRAFANA_PASSWORD` in `.env`. If the Grafana named volume already has an admin password, changing `.env` will not reset the stored Grafana user. |
| Dashboard or datasource is missing | Check Grafana logs and ensure both provisioning directories and dashboard JSON exist. Restart Grafana after provisioning file changes with `docker compose restart grafana`. |
| Panels show no data | Check `http://localhost:9090/targets` for `fastapi` **UP**. Open `http://localhost:8000/metrics`, generate API requests, and widen Grafana's time range. |
| API target is DOWN | Check `docker compose logs --tail=100 api`, then test `http://localhost:8000/health`. The API container health check must pass before Prometheus starts. |
| Health probe is DOWN | Check `docker compose logs --tail=100 blackbox` and confirm `prometheus/blackbox.yml` and the `fastapi-health` scrape configuration are valid. |
| Alerts do not fire | Check Prometheus `/alerts` and `/rules`, confirm the relevant HTTP status was scraped at `/metrics`, and allow for the rule's scrape window and `for` time. |
| Compose reports port/access errors | Resolve Docker Engine permissions or free the occupied host port, then run `docker compose up -d` again. |

Useful commands from this directory:

```powershell
docker compose ps
docker compose logs --tail=100 api prometheus grafana alertmanager blackbox
docker compose restart api
docker compose down
```

## Maintenance process

1. Review Grafana trends, Prometheus targets and alerts, Alertmanager status, and
   `logs/api.log` during routine checks.
2. After changing API thresholds, set `ALERT_LATENCY_MS` or
   `ALERT_ERROR_PERCENT` in `.env` and recreate the API container.
3. After changing Prometheus scrape or rule files, restart Prometheus. After
   changing Grafana provisioning, restart Grafana. After changing notification
   settings, restart Alertmanager.
4. Keep credentials out of source control. Replace example Grafana and
   Alertmanager credentials before sharing or deploying the stack.
5. Review container image versions before upgrades. Back up named volumes before
   upgrades or cleanup; `docker compose down -v` deletes persisted monitoring
   data.
6. Check the size of `logs/api.log` and rotate/archive it periodically; the
   current file redirection appends logs and does not rotate them automatically.

## Tests

Install test dependencies and run pytest from the repository root:

```powershell
python -m pip install -r New1/requirements-dev.txt
python -m pytest New1/tests -q
```

Database tests use in-memory SQLite and do not require a running PostgreSQL
server.
<img width="956" height="503" alt="image" src="https://github.com/user-attachments/assets/f0779f3b-64c3-4f77-bd73-82b360eb8e21" />
