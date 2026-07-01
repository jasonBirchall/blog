# Observability (N6.7)

A self-hosted Prometheus + Alertmanager stack, all rootless Podman quadlets on
`blog.network`. Exporters are internal (never published); the Prometheus and
Alertmanager UIs bind to host loopback and are reached **over Tailscale only**.

## Components

| Quadlet                       | Image                              | Role                              | Published        |
| ----------------------------- | ---------------------------------- | --------------------------------- | ---------------- |
| `node-exporter.container`     | prometheus/node-exporter           | host CPU/mem/disk                 | no (internal)    |
| `podman-exporter.container`   | navidys/prometheus-podman-exporter | per-container state               | no               |
| `blackbox-exporter.container` | prometheus/blackbox-exporter       | probes the public URL (up + cert) | no               |
| `prometheus.container`        | prometheus/prometheus              | scrape + rules                    | `127.0.0.1:9090` |
| `alertmanager.container`      | prometheus/alertmanager            | routing → email + Watchdog        | `127.0.0.1:9093` |

Litestream (N6.5) exposes its own metrics on `:9090` (config `addr`), scraped as
`litestream:9090`.

Config files in this directory are bind-mounted read-only into the containers:
`prometheus.yml`, `rules.yml`, `alertmanager.yml`, `blackbox.yml`.

## Alerts (`rules.yml`)

Five deliberately small, actionable rules — each carries a remediation command in
its annotation (solo blog, one inbox, no on-call: alert only on things that need a
human, everything else is a dashboard):

- **`Watchdog`** — always firing; drives the healthchecks.io dead-man's switch.
- **`BlogDown`** (critical) — public site not returning 2xx for 2m.
- **`TargetDown`** (warning) — a container/exporter stopped being scraped; if
  `job=litestream`, off-box backups have paused.
- **`CertExpiringSoon`** (warning) — TLS cert < 14 days from expiry.
- **`DiskFillingUp`** (warning) — < 15% disk free.

Validate then hot-reload (no restart — Prometheus runs `--web.enable-lifecycle`):

```sh
podman exec prometheus promtool check rules /etc/prometheus/rules.yml
curl -sXPOST http://localhost:9090/-/reload
```

## Routing (`alertmanager.yml`)

- **Email** for triggered alarms:
  The token is the `proton_smtp_token` podman secret, mounted as a file and read
  via `smtp_auth_password_file` — never inline.
- **Watchdog** → webhook to a healthchecks.io check on a 1-minute repeat. If
  Prometheus or Alertmanager dies, the pings stop and healthchecks alerts. The
  ping URL is rendered from `watchdog_healthchecks_url` (sops) at provision time;
  do not commit the real UUID.

## Accessing the UIs

The UIs bind to `127.0.0.1` on the box — never public. Two ways in:

**SSH tunnel — simplest, works immediately** (forwards the loopback ports over
your existing `ssh blog`):

```sh
ssh -N -L 9090:localhost:9090 -L 9093:localhost:9093 blog
# then, in a browser:  http://localhost:9090  (Prometheus)  ·  http://localhost:9093  (Alertmanager)
```

**Tailscale Serve — durable, nicer URL** (TLS, tailnet-only; needs MagicDNS +
HTTPS enabled for the tailnet):

```sh
tailscale serve --bg --https=9090 127.0.0.1:9090   # Prometheus
tailscale serve --bg --https=9093 127.0.0.1:9093   # Alertmanager
# then:  https://blog.<tailnet>.ts.net:9090  and  :9093
```

### What to look at

- **Prometheus → Status → Targets** (`/targets`) — every target should be **UP** (6 of them).
- **Prometheus → Alerts** (`/alerts`) — `Watchdog` **FIRING** is correct (always on);
  the rest **INACTIVE** unless something's actually wrong.
- **Alertmanager** (`:9093`) — active alerts; `Watchdog` shows perpetually, by design.

### Starter queries (Prometheus → Graph)

```promql
probe_success{job="blackbox-http"}                  # 1 = site is serving 2xx (THE one that matters)
(probe_ssl_earliest_cert_expiry - time()) / 86400   # TLS cert: days until expiry
up                                                  # every scrape target, 1 = up
100 * node_filesystem_avail_bytes{fstype=~"ext4|xfs|btrfs"} / node_filesystem_size_bytes{fstype=~"ext4|xfs|btrfs"}   # disk free %
```

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

- Fire a synthetic alert → email arrives (~30s):

    ```sh
    podman exec alertmanager amtool alert add alertname=TestEmail severity=warning \
      --alertmanager.url=http://localhost:9093
    ```

- Pause the Watchdog healthchecks check → its heartbeat page goes red.
- `systemctl --user stop app` → `BlogDown` fires within ~2–3 min (disruptive — blips
  the live site; `systemctl --user start app` to recover).
