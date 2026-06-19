# Runbook

How to rebuild and operate the blog. Target: a working box from scratch in under
an hour. Written **as performed** — every step below was actually run, and
the gotchas are the ones that actually bit.

## Architecture in one breath

Hetzner CPX22 (cost-optimised x86, `hel1`), rootless **Podman quadlets** on a
user network `blog.network`: **Caddy** (TLS + deny rules + privacy logs) →
**app** (gunicorn, Django prod) → **SQLite** on a named volume, with
**Litestream** streaming that volume to **Hetzner Object Storage**. Deploys are
**pull-based**: a `blog`-user systemd timer fetches `main` and rebuilds. Admin is
**Tailscale-only** (no public SSH). `content/` in git is the source of truth; the
SQLite DB is a derived artefact — so a lost DB is rebuildable from git.

State of the world is in:

- `deploy/tofu/` — infra (server, firewall, Object Storage bucket, apex DNS).
- `deploy/cloud-init.yaml.tftpl` — the OS bootstrap (runs automatically on a fresh box).
- `deploy/bootstrap-existing-box.md` — the same recipe by hand (only for adopting a pre-existing box).
- `deploy/quadlets/`, `deploy/caddy/`, `deploy/litestream/`, `deploy/Containerfile` — the app stack.
- `deploy/systemd/` — the deploy timer.
- `deploy/secrets/` — sops + age; how secrets reach the box.

---

## Part 1 — Rebuild from zero

### Prerequisites (laptop)

- `sops`, `age`, and **your age private key** at `~/.config/sops/age/keys.txt`
  (the one thing that is irreplaceable — see `deploy/secrets/README.md`).
- `tofu`, and optionally the `hcloud` CLI.
- `deploy/secrets/secrets.sops.yaml` decryptable, and `deploy/tofu/terraform.tfvars`
  filled (non-secret inputs). A **fresh Tailscale auth key** (tagged `tag:server`,
  single-use) in the sops file's `TF_VAR_tailscale_auth_key`.

### 1. Provision the infrastructure (tofu, from the laptop)

A fresh `tofu apply` creates the server **and cloud-init runs the entire OS
bootstrap automatically** (packages incl. `git`/`aardvark-dns`/`passt`, the
`ip_unprivileged_port_start`+`ip_nonlocal_bind` sysctls, Tailscale, hardened
sshd, linger). You do **not** run `bootstrap-existing-box.md` for a fresh box —
that's only for adopting a box that predates cloud-init.

```sh
# first-ever apply: the state bucket doesn't exist yet, so bootstrap local→remote
# (see deploy/tofu/README.md "First-apply bootstrap"). Otherwise:
make tofu-init                      # checksum-safe; skip_s3_checksum is set in versions.tf
make tofu-plan                      # READ IT — expect no destroys
make tofu-apply
```

Gotchas:

- **Hetzner Object Storage is Ceph** — the S3 backend needs `skip_s3_checksum`
  (set in `versions.tf`) and the checksum env vars (baked into the `make tofu-*`
  targets), or `PutObject` 400s.
- **Apex DNS only.** tofu manages `apex_a`/`apex_aaaa`; mail (Proton) and `www`
  (GitHub Pages) stay untouched in Gandi. Import the apex records if they already
  exist (`deploy/tofu/import.tf.example`).
- **Firewall lock-out.** The firewall opens 80/443 only — no public SSH. On a
  fresh box that's fine (Tailscale comes up in cloud-init). On an _adopted_ box,
  do not attach the firewall until tailnet SSH is proven.

### 2. Reach the box

```sh
ssh blog            # over Tailscale (MagicDNS). Public SSH is firewalled off.
umask               # MUST be 0022. If 0177, fix before any git op (see gotchas).
```

If `ssh blog` fails with "connection refused" after a reboot, sshd raced
`tailscale0`; `ip_nonlocal_bind=1` (in cloud-init) prevents it. Break-glass:
Hetzner console → reset root password → web VNC → fix `sshd_config.d/`.

### 3. App-stack provisioning (the manual sequence)

All on the box as `blog`, except the secret-injection (run from the laptop).

**3a. Clone the repo**

```sh
git clone https://codeberg.org/jasonbirchall/blog.git ~/srv/blog
```

HTTPS is anonymous (public repo); integrity comes from the signature gate, not
the transport.

**3b. Podman secrets** — from the **laptop** (the age key never goes on the box):

```sh
while read -r sops_key pod_name; do
  sops -d --extract "[\"$sops_key\"]" deploy/secrets/secrets.sops.yaml | tr -d '\n' \
    | ssh blog "podman secret create $pod_name -"
done <<'EOF'
django_secret_key                django_secret_key
proton_smtp_token                proton_smtp_token
TF_VAR_object_storage_access_key object_storage_access_key
TF_VAR_object_storage_secret_key object_storage_secret_key
EOF
```

**3c. Deploy heartbeat file** (optional; from the laptop):

```sh
{ printf 'HEALTHCHECKS_PING_URL='; \
  sops -d --extract '["healthchecks_ping_url"]' deploy/secrets/secrets.sops.yaml | tr -d '\n'; \
  printf '\n'; } \
  | ssh blog 'install -d -m700 ~/.config/blog && umask 177 && cat > ~/.config/blog/deploy.env'
```

**3d. Signature gate** (so the deploy timer's `git verify-commit` passes). On the
**laptop**, emit your signer line, paste it on the box:

```sh
# laptop:
printf '%s %s\n' "$(git config user.email)" "$(awk '{print $1,$2}' "$(git config user.signingkey)")"
```

```sh
# box:
mkdir -p ~/.config/blog
echo 'PASTE_THE_LINE' > ~/.config/blog/allowed_signers
git -C ~/srv/blog config gpg.ssh.allowedSignersFile ~/.config/blog/allowed_signers
git -C ~/srv/blog verify-commit HEAD && echo "VERIFY OK"   # must print
```

**3e. Install the quadlets and build the image**

```sh
mkdir -p ~/.config/containers/systemd
cp ~/srv/blog/deploy/quadlets/blog.network \
   ~/srv/blog/deploy/quadlets/app.container \
   ~/srv/blog/deploy/quadlets/caddy.container \
   ~/srv/blog/deploy/quadlets/litestream.container \
   ~/.config/containers/systemd/
cd ~/srv/blog && podman build -f deploy/Containerfile -t localhost/blog:latest .
```

**3f. Seed the database** (fresh build — for disaster recovery use _Restore_
below instead). Two separate `podman run`s; do NOT wrap them in one `sh -c` (a
pasted line-wrap splits `uv run --no-sync`):

```sh
podman run --rm --volume blog-db:/app/data \
  --env DATABASE_PATH=/app/data/db.sqlite3 --env DJANGO_SETTINGS_MODULE=config.settings.prod \
  --secret django_secret_key,type=env,target=DJANGO_SECRET_KEY \
  localhost/blog:latest uv run --no-sync python manage.py migrate --noinput
podman run --rm --volume blog-db:/app/data \
  --env DATABASE_PATH=/app/data/db.sqlite3 --env DJANGO_SETTINGS_MODULE=config.settings.prod \
  --secret django_secret_key,type=env,target=DJANGO_SECRET_KEY \
  localhost/blog:latest uv run --no-sync python manage.py sync_content
```

**3g. Start the stack**

```sh
systemctl --user daemon-reload
systemctl --user start app.service caddy.service litestream.service
podman ps --format '{{.Names}}'      # expect: app, systemd-caddy, litestream
```

Quadlets carry `[Install] WantedBy=default.target`, so with linger they restart
on boot automatically — no `enable` needed.

**3h. Deploy timer**

```sh
cp ~/srv/blog/deploy/systemd/blog-deploy.service \
   ~/srv/blog/deploy/systemd/blog-deploy.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now blog-deploy.timer
```

**3i. Observability (N6.7)** — see `deploy/observability/README.md` (TODO once landed).

### 4. Verify it's live

```sh
curl -I https://jasonbirchall.dev                         # 200 (first hit lags while ACME runs)
ssh blog 'journalctl --user -u litestream -n 5 --no-pager'  # "wal segment written"
ssh blog 'systemctl --user list-timers blog-deploy.timer'   # armed
```

End-to-end deploy test: push a trivial commit to `main`, watch it go live in ≤2 min.

---

## Part 2 — Operating

### Manual deploy (bypass the timer)

```sh
ssh blog 'systemctl --user start blog-deploy.service && journalctl --user -u blog-deploy.service -n 40 --no-pager'
```

### Roll back a bad commit

`git revert <sha>` on the laptop, push — the timer redeploys the revert in ≤2 min.
(An already-Wayback-snapshotted post stays in the Wayback Machine permanently.)

### Restore the DB from Litestream (disaster recovery)

Instead of _seed_ (3f), pull the latest replica into the volume, then start the app:

```sh
podman run --rm --volume blog-db:/app/data \
  --volume ~/srv/blog/deploy/litestream/litestream.yml:/etc/litestream.yml:ro,Z \
  --secret object_storage_access_key,type=env,target=LITESTREAM_ACCESS_KEY_ID \
  --secret object_storage_secret_key,type=env,target=LITESTREAM_SECRET_ACCESS_KEY \
  docker.io/litestream/litestream:0.3 restore -config /etc/litestream.yml /app/data/db.sqlite3
```

### Rotate a secret

See `deploy/secrets/README.md` "Rotating a box secret": edit the sops file,
`podman secret rm` + re-create on the box, restart the consumer.

### Reach the box if Tailscale is down

There is no public SSH fallback by design — use the **Hetzner web console** (VNC).
Reset the root password there if needed (console login isn't SSH, so
`PermitRootLogin no` doesn't block it).

---

## Gotchas reference (the things that actually bit)

- **`aardvark-dns` must be installed** — container name resolution on `blog.network`
  (Caddy → `app:8000`). Missing → 502 "no such host".
- **Quadlets need `ContainerName=<short>`** — otherwise the container is
  `systemd-<unit>` and the short name won't resolve via aardvark.
- **Login umask `0177` corrupts git** — it strips the execute bit off new dirs, so
  `.git/objects/` fan-out dirs become non-traversable ("insufficient permission for
  adding an object"). Fix: `umask 022`, uncomment `umask 022` in `~/.profile`, and
  `UMask=0022` is pinned on the deploy service. Verify `umask` == `0022` early.
- **`ip_nonlocal_bind=1`** — lets sshd bind the tailnet IP before `tailscale0` is up,
  so a reboot doesn't lock you out.
- **`skip_s3_checksum`** — Hetzner Ceph rejects AWS integrity checksums on the tofu
  S3 backend.
- **`passt`** — Podman 5's default rootless network backend; missing → `podman run` fails.
- **Apex only** — Caddy serves `jasonbirchall.dev`, not `www` (which is GitHub Pages);
  claiming `www` makes ACME fail.
- **Firewall before Tailscale = lock-out** — only attach the 80/443 firewall once
  tailnet SSH is proven.
