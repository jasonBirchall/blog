#!/usr/bin/env bash
# Pull-based deploy (N6.6). Invoked every two minutes by blog-deploy.timer (user
# scope). Fetches main; if it moved, rebuilds the image and runs a one-shot
# (migrate, sync_content, then a best-effort snapshot_posts), restarts the app,
# and pings the heartbeat. Any failure leaves the previous image serving and
# exits non-zero, which fires the /fail ping (alerting wired in N6.7). No
# CI-held SSH keys, no inbound SSH, no push pipeline — the box pulls.
set -euo pipefail

REPO_DIR="${BLOG_REPO_DIR:-$HOME/srv/blog}"
# Anonymous HTTPS read (public repo): no credential on the box. Integrity comes
# from the verify-commit signature gate below, not the transport.
CANONICAL_REMOTE="${BLOG_REMOTE:-https://codeberg.org/jasonbirchall/blog.git}"
IMAGE="localhost/blog:latest"
BRANCH="main"
HEARTBEAT_URL="${HEALTHCHECKS_PING_URL:-}"

# Heartbeat helper. Healthchecks-style: a plain GET means success; the same URL
# with a /fail suffix signals failure. Never let a ping failure abort the deploy.
ping() { [ -n "$HEARTBEAT_URL" ] && curl -fsS -m 10 -o /dev/null "$1" || true; }
# Deliberate refusal: alert and stop. The ERR trap covers *unexpected* failures
# (build, migrate) but does not fire on an explicit `exit`, so integrity-gate
# failures ping /fail here.
fail() { echo "deploy refused: $1" >&2; ping "${HEARTBEAT_URL%/}/fail"; exit 1; }
trap 'ping "${HEARTBEAT_URL%/}/fail"' ERR

cd "$REPO_DIR"

# Re-assert the canonical remote each run so a tampered .git/config self-heals
# back to Codeberg before we trust origin/$BRANCH.
git remote set-url origin "$CANONICAL_REMOTE"

git fetch --quiet origin "$BRANCH"
target="$(git rev-parse "origin/$BRANCH")"

if [ "$(git rev-parse HEAD)" = "$target" ]; then
  ping "$HEARTBEAT_URL"   # liveness: timer fired, nothing new to deploy
  exit 0
fi

# Integrity gates — verify the tip before touching the working tree.
# 1. Fast-forward only: HEAD must be an ancestor of the target, so the box only
#    ever moves forward on $BRANCH. Refuses rewinds, force-pushes, divergence.
git merge-base --is-ancestor HEAD "$target" \
  || fail "origin/$BRANCH ($target) is not a fast-forward of HEAD (possible force-push)"
# 2. Signature gate: the tip must carry a valid signature from an allowed key,
#    enforcing the signed-commits rule at the edge. Needs gpg.ssh.allowedSignersFile
#    (SSH) or a trusted keyring (GPG) on the box; see deploy/systemd/README.md.
git verify-commit "$target" >/dev/null 2>&1 \
  || fail "tip commit $target is not signed by an allowed key"

echo "Deploying $(git rev-parse --short HEAD) -> $(git rev-parse --short "$target")"
git reset --hard "$target"

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
