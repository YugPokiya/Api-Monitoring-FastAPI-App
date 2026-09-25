# Grafana provisioning

Grafana reads provisioning YAML files from this folder at container startup.
Compose mounts this directory read-only at `/etc/grafana/provisioning`.

- `datasources/` declares Prometheus as the default query source.
- `dashboards/` declares a file provider that loads JSON dashboards from
  `/var/lib/grafana/dashboards` into the **API Monitoring** folder.

The provider and datasource have their own README files with setting details.
Restart Grafana after editing provisioning YAML:

```powershell
docker compose restart grafana
```
