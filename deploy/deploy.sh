#!/usr/bin/env bash
# Pull-based deploy (N6.6). Invoked every two minutes by blog-deploy.timer (user
# scope). Fetches main; if it moved, rebuilds the image and runs a one-shot
# (migrate, sync_content, then a best-effort snapshot_posts), restarts the app,
# and pings the heartbeat. Any failure leaves the previous image serving and
# exits non-zero, which fires the /fail ping (alerting wired in N6.7). No
# CI-held SSH keys, no inbound SSH, no push pipeline — the box pulls.
set -euo pipefail

REPO_DIR="${BLOG_REPO_DIR:-$HOME/srv/blog}"
IMAGE="localhost/blog:latest"
BRANCH="main"
HEARTBEAT_URL="${HEALTHCHECKS_PING_URL:-}"

# Heartbeat helper. Healthchecks-style: a plain GET means success; the same URL
# with a /fail suffix signals failure. Never let a ping failure abort the deploy.
ping() { [ -n "$HEARTBEAT_URL" ] && curl -fsS -m 10 -o /dev/null "$1" || true; }
trap 'ping "${HEARTBEAT_URL%/}/fail"' ERR

cd "$REPO_DIR"

git fetch --quiet origin "$BRANCH"
if [ "$(git rev-parse HEAD)" = "$(git rev-parse "origin/$BRANCH")" ]; then
  ping "$HEARTBEAT_URL"   # liveness: timer fired, nothing new to deploy
  exit 0
fi

echo "Deploying $(git rev-parse --short HEAD) -> $(git rev-parse --short "origin/$BRANCH")"
git reset --hard "origin/$BRANCH"

# Build the new image. If this fails, the old :latest is untouched and serving.
podman build -f deploy/Containerfile -t "$IMAGE" .

# Fatal one-shot: schema and content must apply cleanly or we do not ship.
# Shares the app's named volume so it writes the live db.sqlite3.
podman run --rm \
  --volume blog-db:/app/data \
  --env DATABASE_PATH=/app/data/db.sqlite3 \
  --env DJANGO_SETTINGS_MODULE=config.settings.prod \
  --secret django_secret_key,type=env,target=DJANGO_SECRET_KEY \
  "$IMAGE" \
  sh -c "uv run --no-sync python manage.py migrate --noinput \
      && uv run --no-sync python manage.py sync_content"

# Roll the app onto the new image. The quadlet unit recreates the container
# from localhost/blog:latest, so a restart is enough to pick up the new build.
systemctl --user restart app.service

# Best-effort Wayback snapshot (N5.2): non-fatal, retried on the next deploy.
podman run --rm \
  --volume blog-db:/app/data \
  --env DATABASE_PATH=/app/data/db.sqlite3 \
  --env DJANGO_SETTINGS_MODULE=config.settings.prod \
  --secret django_secret_key,type=env,target=DJANGO_SECRET_KEY \
  "$IMAGE" \
  sh -c "uv run --no-sync python manage.py snapshot_posts" \
  || echo "snapshot_posts failed (non-fatal); the next deploy retries it"

ping "$HEARTBEAT_URL"
echo "Deploy complete."
