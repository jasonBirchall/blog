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

1. `git fetch origin main`. If HEAD is unchanged: ping success (liveness), exit.
2. `git reset --hard origin/main`.
3. `podman build` the new `localhost/blog:latest`. On failure the old image is untouched.
4. One-shot container (shares the app's `blog-db` volume): `migrate` then
   `sync_content`. **Fatal** — a bad migration or bad content stops the deploy here.
5. `systemctl --user restart app.service` — the quadlet recreates the container
   from the new `:latest`.
6. One-shot `snapshot_posts` (Wayback, N5.2). **Best-effort** — failures are
   logged and retried next deploy.
7. Ping the heartbeat success URL.

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

## Secrets the script needs

`deploy.sh` reads `HEALTHCHECKS_PING_URL` (and optionally `BLOG_REPO_DIR`) from
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
