#!/usr/bin/env bash
# WakaTime stats sync one-shot (N.7). Invoked daily by blog-wakatime.timer (user
# scope), decoupled from the deploy timer: deploys fire only when main moves, but
# stats must refresh regardless. Runs manage.py sync_wakatime against the live
# db.sqlite3 in the shared blog-db volume, using the wakatime_api_key podman
# secret. On success, writes a freshness metric to the node_exporter textfile
# collector (N.8); on failure, exits non-zero and writes nothing — staleness is
# the signal, surfaced by the WakaTimeStale alert.
set -euo pipefail

IMAGE="localhost/blog:latest"
# Host path bind-mounted into node-exporter at /host/var/lib/node_exporter/textfile.
TEXTFILE_DIR="${TEXTFILE_DIR:-/var/lib/node_exporter/textfile}"
METRIC="wakatime_last_success_timestamp_seconds"

# Fresh box, first boot before the first deploy: no image yet. Exit clean so the
# timer does not flap; the next deploy builds the image and the following run syncs.
if ! podman image exists "$IMAGE"; then
  echo "no $IMAGE yet; skipping WakaTime sync (first deploy has not run)"
  exit 0
fi

# Fatal one-shot: on any failure the command exits non-zero, leaving the previous
# snapshot row intact (stale beats broken), and set -e stops us before the metric
# write below — so the freshness gauge is not bumped and the alert can fire.
podman run --rm \
  --volume blog-db:/app/data \
  --env DATABASE_PATH=/app/data/db.sqlite3 \
  --env DJANGO_SETTINGS_MODULE=config.settings.prod \
  --secret django_secret_key,type=env,target=DJANGO_SECRET_KEY \
  --secret wakatime_api_key,type=env,target=WAKATIME_API_KEY \
  "$IMAGE" \
  sh -c "uv run --no-sync python manage.py sync_wakatime"

# Success only. Write the freshness metric atomically (.tmp + mv) so a concurrent
# scrape never reads a half-written file.
tmp="$TEXTFILE_DIR/wakatime.prom.tmp"
dest="$TEXTFILE_DIR/wakatime.prom"
{
  echo "# HELP $METRIC Unixtime of last successful WakaTime sync."
  echo "# TYPE $METRIC gauge"
  echo "$METRIC $(date +%s)"
} >"$tmp"
mv "$tmp" "$dest"
echo "WakaTime sync complete; wrote $dest"
