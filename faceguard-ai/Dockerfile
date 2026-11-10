# FaceGuard AI as ONE container: the FastAPI backend also serves the built React app.
# For Render, Railway, Fly.io or any VPS:  docker build -t faceguard . && docker run -p 8000:8000 -e JWT_SECRET=... faceguard
# (docker-compose.yml is the separate multi-container setup with PostgreSQL and an Nginx gateway.)

# ---- 1. build the web app ----
FROM node:22-alpine AS web
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2. API + static files ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/alembic.ini ./
COPY backend/scripts ./scripts
COPY backend/migrations ./migrations
COPY backend/app ./app
# Landmark model (54 MB) is downloaded and SHA-256 verified at build time.
RUN python scripts/fetch_models.py
COPY --from=web /app/dist ./static
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 755 /usr/local/bin/docker-entrypoint.sh \
 && useradd --system --uid 10001 --no-create-home faceguard \
 && mkdir -p /srv/data && chown faceguard /srv/data

# Defaults suitable for a hosted single container. Override any of them with platform environment variables.
#  - DATABASE_URL: empty = SQLite file on the /srv/data volume. Set a postgres:// URL to use PostgreSQL instead.
#  - JWT_SECRET: REQUIRED (32+ random characters). The container refuses to start without it.
ENV DATA_DIR=/srv/data FRONTEND_DIR=/srv/static ENVIRONMENT=production DOCS_ENABLED=false PORT=8000 MALLOC_ARENA_MAX=2 OMP_NUM_THREADS=1 OPENCV_NUM_THREADS=1
VOLUME /srv/data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=5 \
  CMD python -c "import os,json,urllib.request as u; d=json.load(u.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health', timeout=4)); raise SystemExit(0 if d['status']=='ok' else 1)"

ENTRYPOINT ["docker-entrypoint.sh"]
