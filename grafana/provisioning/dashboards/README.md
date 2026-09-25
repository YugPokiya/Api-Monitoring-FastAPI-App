# Grafana dashboard provider

`provider.yml` registers a file-based dashboard provider named **API
Monitoring**. It loads JSON files from `/var/lib/grafana/dashboards`, which
Compose maps to the local `grafana/dashboards/` directory.

The provider's `folder` setting controls the Grafana folder. `disableDeletion`
prevents provisioning from deleting provisioned dashboards, and `editable`
allows UI edits. For durable, reviewable changes, update the JSON source file;
UI-only edits may be overwritten when the dashboard is provisioned again.

After changing the provider configuration, restart Grafana with
`docker compose restart grafana`.
