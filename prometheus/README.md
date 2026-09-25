# Prometheus configuration

Prometheus scrapes the FastAPI metrics endpoint and evaluates alert rules from
this folder. Compose mounts this directory read-only at `/etc/prometheus` and
stores time series in the `prometheus_data` named volume (15-day retention).

## Files

- `prometheus.yml` sets a 5-second scrape and evaluation interval; configures
  FastAPI, Prometheus self-scraping, and the Blackbox health probe; and points
  alert delivery to Alertmanager.
- `alerts.yml` contains availability, latency, HTTP error, authentication, rate
  limit, timeout, and failure-rate rules.
- `blackbox.yml` defines the `http_2xx` HTTP probe used for `/health`.
- `Promexa.py` is a standalone Flask/Prometheus example and is **not** used by
  Docker Compose. Compose monitors `monitoring.py` instead. The sample starts a
  Flask server on port 5000 and a metrics server on port 8000 if run directly.

Prometheus targets and rules can be inspected at
`http://localhost:9090/targets`, `/rules`, and `/alerts`. After editing scrape or
rule configuration, restart Prometheus:

```powershell
docker compose restart prometheus
```

Validate that targets return **UP** and rule files load without errors before
relying on alert notifications. Prometheus sends alert events to the
Alertmanager service; notification receivers are configured separately in
`../alertmanager/alertmanager.yml`.
