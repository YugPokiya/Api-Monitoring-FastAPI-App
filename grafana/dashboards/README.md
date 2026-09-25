# Provisioned dashboards

`api-monitoring.json` defines the **FastAPI Monitoring** dashboard. It uses the
Prometheus datasource UID `prometheus` and displays availability, request rate,
failure percentage, p50/p95/p99 latency, status codes, host CPU and memory,
uptime, and failed requests grouped by endpoint.

The dashboard is loaded by the file provider in
`../provisioning/dashboards/provider.yml`. Edit the JSON to change panels or
PromQL. Keep query labels consistent with the metrics exported by
`monitoring.py`. If updates do not appear, check Grafana logs and restart the
Grafana service. Generate API traffic to populate rate and latency panels.
