# Alertmanager configuration

`alertmanager.yml` configures how Prometheus alerts are grouped, routed, and
sent. Compose mounts this folder read-only at `/etc/alertmanager` and stores
Alertmanager state in the `alertmanager_data` named volume.

The current configuration groups alerts by alert name and job and defines email
and Slack receivers. Replace the example SMTP, recipient, webhook, and channel
values with valid private settings before expecting notifications. Do not
commit credentials or real webhook URLs.

The web interface is at `http://localhost:9093`; use it to inspect active
alerts and manage silences. Review startup errors with
`docker compose logs --tail=100 alertmanager`. Restart after changing the
configuration:

```powershell
docker compose restart alertmanager
```
