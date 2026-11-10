#!/bin/sh
# Starts FaceGuard AI in single-container mode (see Dockerfile).
set -eu

if [ -z "${JWT_SECRET:-}" ]; then
  echo "ERROR: set JWT_SECRET (at least 32 random characters), e.g. the output of: openssl rand -hex 32" >&2
  exit 1
fi

# No DATABASE_URL: keep a SQLite database on the data volume.
export DATABASE_URL="${DATABASE_URL:-sqlite:////srv/data/faceguard.db}"

# Public address: Render and Railway announce it; otherwise use APP_BASE_URL if you set one.
if [ -z "${APP_BASE_URL:-}" ]; then
  if [ -n "${RENDER_EXTERNAL_URL:-}" ]; then APP_BASE_URL="$RENDER_EXTERNAL_URL"
  elif [ -n "${RAILWAY_PUBLIC_DOMAIN:-}" ]; then APP_BASE_URL="https://$RAILWAY_PUBLIC_DOMAIN"
  else APP_BASE_URL="http://localhost:${PORT}"; fi
fi
export APP_BASE_URL
# The web app is served from the same origin as the API, so this only matters for other origins.
export CORS_ORIGINS="${CORS_ORIGINS:-$APP_BASE_URL}"

run() {
  # Platform volumes are often mounted root-owned: fix ownership, then drop to the unprivileged user.
  if [ "$(id -u)" = "0" ]; then
    chown -R faceguard /srv/data 2>/dev/null || true
    exec setpriv --reuid=10001 --regid="$(id -g faceguard)" --clear-groups -- "$@"
  fi
  exec "$@"
}

run sh -c '
  alembic upgrade head &&
  exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers --forwarded-allow-ips "*"
'
