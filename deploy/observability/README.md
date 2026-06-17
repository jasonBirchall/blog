# Observability (N6.7)

A self-hosted Prometheus + Alertmanager stack, all rootless Podman quadlets on
`blog.network`. Exporters are internal (never published); the Prometheus and
Alertmanager UIs bind to host loopback and are reached **over Tailscale only**.

## Components

| Quadlet | Image | Role | Published |
|---|---|---|---|
| `node-exporter.container` | prometheus/node-exporter | host CPU/mem/disk | no (internal) |
| `podman-exporter.container` | navidys/prometheus-podman-exporter | per-container state | no |
| `blackbox-exporter.container` | prometheus/blackbox-exporter | probes the public URL (up + cert) | no |
| `prometheus.container` | prometheus/prometheus | scrape + rules | `127.0.0.1:9090` |
| `alertmanager.container` | prometheus/alertmanager | routing → email + Watchdog | `127.0.0.1:9093` |

Litestream (N6.5) exposes its own metrics on `:9090` (config `addr`), scraped as
`litestream:9090`.

Config files in this directory are bind-mounted read-only into the containers:
`prometheus.yml`, `rules.yml`, `alertmanager.yml`, `blackbox.yml`.

## Alerts (`rules.yml`)

`Watchdog` (always firing, drives the dead man's switch), `InstanceDown`,
`BlogDown` (public probe), `AppContainerDown`, `DiskSpaceLow`, `CertExpiringSoon`,
`LitestreamReplicationLag`, `DeployStale`. Thresholds are starting points; some
metric names are marked TODO because they depend on the exact exporter build —
confirm against each `/metrics` before relying on them.

## Routing (`alertmanager.yml`)

- **Email** for everything → `me@jasonbirchall.dev` via `smtp.protonmail.ch:587`.
  The token is the `proton_smtp_token` podman secret, mounted as a file and read
  via `smtp_auth_password_file` — never inline.
- **Watchdog** → webhook to a healthchecks.io check on a 1-minute repeat. If
  Prometheus or Alertmanager dies, the pings stop and healthchecks alerts. The
  ping URL is rendered from `watchdog_healthchecks_url` (sops) at provision time;
  do not commit the real UUID.

## Exposing the UIs over Tailscale

The UIs are bound to `127.0.0.1`, so they are not on the public interface. Expose
them on the tailnet with Tailscale Serve (TLS, tailnet-only):

```sh
tailscale serve --bg --https=9090 127.0.0.1:9090   # Prometheus
tailscale serve --bg --https=9093 127.0.0.1:9093   # Alertmanager
```

(Or reach them with `ssh -L` over Tailscale — but Serve is the durable path.)

## Install on the box

```sh
# enable the rootless podman socket the exporter reads
systemctl --user enable --now podman.socket
# node_exporter textfile dir (for the optional deploy metric)
mkdir -p ~/var/lib/node_exporter/textfile   # adjust to the / bind in the quadlet
cp deploy/quadlets/*.container ~/.config/containers/systemd/
systemctl --user daemon-reload
systemctl --user start prometheus alertmanager node-exporter podman-exporter blackbox-exporter
```

## External uptime check

The Watchdog covers "is monitoring alive". Independently, configure a **third-party**
uptime check (e.g. healthchecks.io is for the dead-man's switch; use an external
HTTP monitor such as Hetzner/UptimeRobot/Better Stack) hitting the public URL, so
an outage that takes the whole box offline — Prometheus included — is still caught.

## DoD checks (on the box)

- Fire a synthetic alert (`amtool alert add Test severity=warning` or a temporary
  always-on rule) → email arrives.
- Pause the Watchdog healthchecks check → its heartbeat page goes red.
- `systemctl --user stop app` → `BlogDown`/`AppContainerDown` fires within ~2 min.
