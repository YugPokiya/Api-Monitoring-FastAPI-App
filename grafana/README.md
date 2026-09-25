# Grafana configuration

This folder contains Grafana's provisioned dashboard and startup configuration.
Docker Compose mounts `provisioning/` read-only at
`/etc/grafana/provisioning` and `dashboards/` read-only at
`/var/lib/grafana/dashboards`. Grafana loads these files when its container
starts. Dashboard state and Grafana users are stored separately in the
`grafana_data` named volume.

## Contents

- `provisioning/datasources/prometheus.yml` adds Prometheus as the default data
  source. It uses `http://prometheus:9090`, the Prometheus service name on the
  internal Compose network.
- `provisioning/dashboards/provider.yml` tells Grafana to load dashboard JSON
  files from `/var/lib/grafana/dashboards` into the **API Monitoring** folder.
- `dashboards/api-monitoring.json` defines the FastAPI Monitoring dashboard and
  its PromQL panels.

After `docker compose up -d`, open `http://localhost:3000`, sign in, and choose
**Dashboards > API Monitoring > FastAPI Monitoring**. If provisioning files
change, restart Grafana with `docker compose restart grafana`.

The datasource and dashboard files are mounted read-only; edit their local
copies here. Do not put credentials in dashboard JSON. Grafana credentials are
configured through `GRAFANA_USER` and `GRAFANA_PASSWORD` in the Compose
environment.
