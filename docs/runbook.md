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
wakatime_api_key                 wakatime_api_key
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

**3j. WakaTime stats sync** (the `/now` page's stats; N.7). The `wakatime_api_key`
podman secret is already created in 3b. Create the metric directory the sync
writes to (node-exporter reads it read-only, so it must be **writable by the
`blog` user**), install the daily timer, and force the first run:

```sh
# metric dir — needs root to create under /var/lib, owned by the blog user
sudo install -d -o blog -g blog -m 755 /var/lib/node_exporter/textfile

cp ~/srv/blog/deploy/systemd/blog-wakatime.service \
   ~/srv/blog/deploy/systemd/blog-wakatime.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now blog-wakatime.timer

systemctl --user start blog-wakatime.service                    # force the first sync
journalctl --user -u blog-wakatime.service -n 20 --no-pager     # "sync complete; wrote …"
cat /var/lib/node_exporter/textfile/wakatime.prom               # the freshness metric
```

The sync is **decoupled** from the deploy timer (stats refresh daily regardless
of commits). The script no-ops cleanly if `localhost/blog:latest` doesn't exist
yet, so ordering against 3e is not critical. The `/now` page renders the prose
from `content/now.md` plus these stats — but it **stays 404 until `now.md` is
`status: published`** (that flip is the go-live switch).

### 4. Verify it's live

```sh
curl -I https://jasonbirchall.dev                         # 200 (first hit lags while ACME runs)
ssh blog 'journalctl --user -u litestream -n 5 --no-pager'  # "wal segment written"
ssh blog 'systemctl --user list-timers blog-deploy.timer'   # armed
```

End-to-end deploy test: push a trivial commit to `main`, watch it go live in ≤2 min.

---

## Rebuild drill

Prove this runbook on a **throwaway box** without touching prod. Isolation is the
whole game — keep these four separate from production:

- **tofu state** — create the drill box _outside_ prod tofu (`hcloud` CLI), so a

    stray apply can't touch the live server.

- **Tailscale hostname** — `blog-drill`, not `blog` (or it collides on the tailnet).
- **apex DNS** — never repoint `jasonbirchall.dev`. Use a throwaway TLS name.
- **Litestream** — skip it, or point `path:` at a `drill/` prefix; never the prod stream.

### Run it

```sh
# laptop: render the cloud-init with drill values + a FRESH single-use Tailscale key
TS_KEY='tskey-auth-…'                      # generate a new one; the sops one is consumed
SSH_KEY="$(cat ~/.ssh/id_ed25519.pub)"
python3 - "$TS_KEY" "$SSH_KEY" > /tmp/drill-cloud-init.yaml <<'PY'
import sys; ts, ssh = sys.argv[1], sys.argv[2]
t = open('deploy/cloud-init.yaml.tftpl').read()
t = (t.replace('${tailscale_auth_key}', ts)
      .replace('${service_user}', 'blog')
      .replace('${ssh_authorized_key}', ssh)
      .replace('--hostname=blog', '--hostname=blog-drill'))
print(t)
PY

# create the box (no firewall needed — sshd is tailnet-bound; ACME needs 80/443 open)
hcloud server create --name blog-drill --type cpx22 --image debian-13 \
  --user-data-from-file /tmp/drill-cloud-init.yaml
```

Then **verify the OS layer** (this is the real test — cloud-init has never been run
before; prod was hand-bootstrapped):

```sh
ssh blog@blog-drill           # tailnet SSH works?
umask                         # 0022?
command -v git aardvark-dns pasta && podman info >/dev/null && echo OK   # packages?
sysctl net.ipv4.ip_unprivileged_port_start net.ipv4.ip_nonlocal_bind     # 80 and 1?
```

Then the **app stack** — follow Part 1 §3, with two drill tweaks:

- After cloning, edit `~/srv/blog/deploy/caddy/Caddyfile` site address to
  `<public-ip>.sslip.io` (resolves to the box, so ACME issues a real cert with no
  DNS change), or use Caddy's internal CA and `curl -k`.
- Skip the Litestream unit (the DB is derived), or set its `path: drill/db.sqlite3`.

Verify: `curl -I https://<public-ip>.sslip.io` → 200. **Time the whole thing.**

### Tear down

```sh
hcloud server delete blog-drill
# then remove the blog-drill node in the Tailscale admin console
```

Update this runbook with anything that was wrong — that's what keeps it true.

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

### Force a WakaTime sync

```sh
ssh blog 'systemctl --user start blog-wakatime.service && journalctl --user -u blog-wakatime.service -n 20 --no-pager'
```

Runs the daily sync now instead of waiting for the timer. On success it upserts
the one `WakaSnapshot` row and bumps the freshness metric; on failure it exits
non-zero and leaves the previous row and metric untouched — stale beats broken.

### Rotate the WakaTime key

Regenerate at wakatime.com/api-key, update the sops file, then swap the podman
secret. **No app restart** is needed — the sync is a one-shot that reads the
secret fresh each run, so the next run (or a forced one) picks up the new value:

```sh
make secrets-edit                      # set wakatime_api_key to the new value; save re-encrypts
ssh blog 'podman secret rm wakatime_api_key'
sops -d --extract '["wakatime_api_key"]' deploy/secrets/secrets.sops.yaml | tr -d '\n' \
  | ssh blog 'podman secret create wakatime_api_key -'
ssh blog 'systemctl --user start blog-wakatime.service'   # confirm the new key works
```

### The WakaTimeStale alert

Fires when the last successful sync is > 48h old (`for: 1h`). 48h tolerates one
missed daily run (a WakaTime blip); two misses means something is actually wrong.
The page keeps serving the last snapshot with an honest "as of" date throughout —
the alert, not a 500, is the signal. Triage:

```sh
ssh blog 'systemctl --user status blog-wakatime.service'
ssh blog 'journalctl --user -u blog-wakatime -n 50 --no-pager'
```

Most likely a revoked/expired key (check wakatime.com/api-key; rotate above) or a
WakaTime outage.

**Rule changes need a Prometheus reload.** A deploy lands a changed `rules.yml` on
the box but does *not* reload Prometheus (it restarts only the app). After a
deploy that touches the rules:

```sh
ssh blog 'podman exec prometheus promtool check rules /etc/prometheus/rules.yml'  # validate
ssh blog 'curl -sS -X POST http://127.0.0.1:9090/-/reload'                        # activate
```

**Synthetic test.** Deleting the metric file does *not* fire this alert — an
absent metric yields no series, which correctly stays quiet (the same reason no
`absent()` guard is needed before the first success). To exercise the firing
path, forge an old timestamp and wait out the `for: 1h`:

```sh
ssh blog 'printf "# TYPE wakatime_last_success_timestamp_seconds gauge\nwakatime_last_success_timestamp_seconds %s\n" \
  $(( $(date +%s) - 49*3600 )) > /var/lib/node_exporter/textfile/wakatime.prom'
# watch Prometheus /alerts go Pending -> Firing, expect the email, then restore reality:
ssh blog 'systemctl --user start blog-wakatime.service'
```

### SSH keys & commit signing

One hardware key (YubiKey, resident FIDO2 `ed25519-sk`, plus a backup) does two
jobs — SSH login *and* commit signing — and **three** trust lists must agree, or
things fail *closed*:

| File | Controls | Format | Failure if a key is missing |
|---|---|---|---|
| box `~/.ssh/authorized_keys` | who can `ssh blog` | `<keytype> <key> <comment>` | login rejected |
| box `~/.config/blog/allowed_signers` | deploy gate — `git verify-commit` on `main`'s tip | `* <keytype> <key>` (leading `*` = any email) | `deploy refused: … not signed by an allowed key` |
| dotfiles `ssh/allowed_signers` (+ `nix/yubikey-ssh.nix`) | local verify of your own commits; each machine's ssh/git config | git allowed_signers | `git log --show-signature`: `No principal matched` |

**The rule:** every key you *sign with* must be in the box's `allowed_signers`;
every key you *log in with* must be in its `authorized_keys`. The box uses a `*`
principal (trust the key for any email) because commits are authored under
several emails.

**Add / rotate a key** (from a machine that can still reach the box):
```sh
cat ~/.ssh/<key>.pub | ssh blog 'cat >> ~/.ssh/authorized_keys'                       # login
awk '{print "*", $1, $2}' ~/.ssh/<key>.pub | ssh blog 'cat >> ~/.config/blog/allowed_signers'  # signing
```
Retire an old key by removing its line from *both* files — but test the new key
(login **and** a signed commit that deploys) before removing the old one, keeping
a session open + the Hetzner console ready.

**A new machine** needs the key material locally: plug in the YubiKey and
`ssh-keygen -K` (pulls the resident handle); the dotfiles (`nix/yubikey-ssh.nix`
on home-manager machines) then wire up `~/.ssh/config` + git signing.

**The two failures this actually caused:**
- *`deploy refused: … not signed by an allowed key`* — a commit signed by a key
  the box doesn't trust (or unsigned). Even a **valid** signature fails if the key
  isn't in `allowed_signers` (git says `No principal matched`). Fix: add the key.
  Fail-closed by design (ADR-0003).
- *`ssh blog` logs in with no touch* — it used the software key (still in
  `authorized_keys` / offered by the agent), not the YubiKey. Force the hardware
  key (`IdentityFile …id_ed25519_sk_rk`, `IdentitiesOnly yes`) and remove the
  software key from `authorized_keys` to require a touch.

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
