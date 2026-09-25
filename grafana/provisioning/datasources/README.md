# Grafana data sources

`prometheus.yml` provisions the Prometheus data source:

- **Name:** Prometheus
- **UID:** `prometheus` (used by dashboard panels)
- **Default:** yes
- **URL:** `http://prometheus:9090`
- **Access:** Grafana server proxy over the Compose network

The hostname is the Compose service name; `localhost` inside Grafana would
refer to the Grafana container itself. The configuration is not editable in the
Grafana UI. Update the YAML and restart Grafana to apply changes. Check the
Grafana data source page or logs if dashboard panels report query errors.
