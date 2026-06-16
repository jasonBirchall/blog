# Pull-based deploy (N6.6)

The box deploys itself. A user-scope systemd timer runs `deploy/deploy.sh` every
two minutes; when `origin/main` moves it rebuilds the image, applies migrations
and content, restarts the app, and pings a heartbeat. Two minutes keeps the
"live within five minutes" SLO with room for the build, at half the log/ping
noise of a one-minute tick. **Nothing pushes to the box** —
no CI-held SSH key, no inbound SSH, no deploy webhook. A bad build or a bad
`sync_content` aborts before the app is touched, so the previous image keeps
serving, and the failure fires the heartbeat's `/fail` URL (alerting: N6.7).

## Flow

1. Re-assert the canonical remote URL (`git remote set-url`), then
   `git fetch origin main`. If HEAD is unchanged: ping success (liveness), exit.
2. **Integrity gates** (ADR-0003) — both refuse the deploy and ping `/fail`:
   - **fast-forward only**: `origin/main` must be a descendant of HEAD, so the box
     only moves forward. Blocks rewinds, force-pushes, and divergence.
   - **signature**: `git verify-commit` on the tip must pass, enforcing the
     signed-commits rule at the edge (see "Commit-signature verification" below).
3. `git reset --hard origin/main`.
4. `podman build` the new `localhost/blog:latest`. On failure the old image is untouched.
5. One-shot container (shares the app's `blog-db` volume): `migrate` then
   `sync_content`. **Fatal** — a bad migration or bad content stops the deploy here.
6. `systemctl --user restart app.service` — the quadlet recreates the container
   from the new `:latest`.
7. One-shot `snapshot_posts` (Wayback, N5.2). **Best-effort** — failures are
   logged and retried next deploy.
8. Ping the heartbeat success URL.

## Install on the box

These are plain user units (unlike the container quadlets, which live in
`~/.config/containers/systemd/`):

```sh
mkdir -p ~/.config/systemd/user
cp deploy/systemd/blog-deploy.service deploy/systemd/blog-deploy.timer ~/.config/systemd/user/
chmod +x deploy/deploy.sh
systemctl --user daemon-reload
systemctl --user enable --now blog-deploy.timer
```

`enable-linger` (set in cloud-init, N6.2) keeps the user manager running after
logout so the timer fires unattended.

## Commit-signature verification (required)

The signature gate calls `git verify-commit`, which for SSH signatures needs an
allowed-signers file **configured at provision time** — without it, verification
errors and *every* deploy is refused (fail-closed and loud, which is the safe
direction but means the site never updates). Set it up once on the box:

```sh
# List the SSH signing key(s) allowed to author deploys.
printf '%s %s\n' "$GIT_AUTHOR_EMAIL" "$(cat ~/.ssh/id_ed25519.pub)" \
  > ~/.config/blog/allowed_signers
git -C ~/srv/blog config gpg.ssh.allowedSignersFile ~/.config/blog/allowed_signers
```

(For GPG-signed commits, import the trusted public key into the box keyring
instead; `git verify-commit` honours whichever signature format the commit uses.)

## Secrets and config the script needs

`deploy.sh` reads `HEALTHCHECKS_PING_URL`, and optionally `BLOG_REPO_DIR` and
`BLOG_REMOTE` (the canonical Codeberg URL it re-asserts each run), from
`~/.config/blog/deploy.env` (mode 600), written from the sops file at provision
time alongside the podman secrets (N6.3). The one-shot containers get
`DJANGO_SECRET_KEY` from the `django_secret_key` podman secret. If `deploy.env`
is absent the heartbeat simply no-ops; the deploy still runs.

## Observe / debug

```sh
systemctl --user list-timers blog-deploy.timer
journalctl --user -u blog-deploy.service -n 50 --no-pager
systemctl --user start blog-deploy.service   # force a deploy check now
```

## Note — supersedes the old push model

The repo checkout on the box is owned and updated by the service user (it runs
`git reset --hard`). This replaces the earlier "deploy user has write access only
to `content/`" baseline, which assumed a push deploy. Reconcile that line in
CLAUDE.md when this lands.
